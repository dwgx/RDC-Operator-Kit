"""Build source archives and an offline project-page preview.

The allowlist intentionally excludes runtime state, local config, downloaded
tools, screenshots, credentials and evidence. No network or publication occurs.
Ordering and metadata are fixed; compressed bytes also depend on the Python
compression runtime. Compare the source manifest across different runtimes.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import html
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {"README.md", "LICENSE", "pyproject.toml", ".gitignore", "AGENTS.md",
              "SECURITY.md", "CHANGELOG.md"}
DIRECTORIES = {"rdc_operator", "scripts", "examples", "tests", "docs", "site", "skills", ".github"}
EXTENSIONS = {".py", ".ps1", ".sh", ".md", ".json", ".yml", ".yaml", ".html", ".css", ".js", ".svg"}
EXCLUDED_PARTS = {"__pycache__", ".git", ".venv", ".venv-mcp", "evidence", "tools", "dist", "build", ".rdc-state",
                  ".pytest_cache"}
EXCLUDED_FILES = {"config.local.json", ".rdc-install.json", ".rdc-delivery.json",
                  "delivery-payload.json", "receive-source.py"}


def _excluded_name(name: str) -> bool:
    name = name.casefold()
    return name in EXCLUDED_PARTS or name in EXCLUDED_FILES or name.endswith(".egg-info")


def _check_source_reference(name: str) -> None:
    # Use canonical POSIX names for archives and preview lookups on every host.
    parts = name.split("/")
    if (any(part in {"", ".", ".."} for part in parts)
            or any(character in name for character in "\\:\x00")):
        raise ValueError(f"Unsafe source reference refused: {name}")
    if any(_excluded_name(part) for part in parts):
        raise ValueError(f"Private source reference refused: {name}")
    allowed = name in ROOT_FILES if len(parts) == 1 else (
        parts[0] in DIRECTORIES and
        (PurePosixPath(name).suffix in EXTENSIONS or parts[-1] == ".nojekyll"))
    if not allowed:
        raise ValueError(f"Source reference outside release allowlist: {name}")


def _source_bytes(sources: dict[str, bytes], name: str) -> bytes:
    _check_source_reference(name)
    try:
        return sources[name]
    except KeyError:
        raise ValueError(f"Source reference missing from release snapshot: {name}") from None


def _source_kind(path: Path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) &
            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
        raise ValueError(f"Linked source refused: {path.relative_to(ROOT)}")
    return info.st_mode


def source_files():
    # Prune before descent; keep cross-platform manifest order.
    files = []
    def visit(directory):
        if not stat.S_ISDIR(_source_kind(directory)):
            raise ValueError(f"Expected source directory: {directory.relative_to(ROOT)}")
        for path in directory.iterdir():
            # Apply the known private names from .gitignore throughout the tree.
            # Casefold also protects bundles prepared on case-sensitive hosts for Windows.
            if _excluded_name(path.name):
                continue
            kind = _source_kind(path)
            if stat.S_ISDIR(kind):
                visit(path)
            elif path.suffix in EXTENSIONS or path.name == ".nojekyll":
                if not stat.S_ISREG(kind):
                    raise ValueError(f"Non-regular source refused: {path.relative_to(ROOT)}")
                files.append(path)
    for name in ROOT_FILES:
        path = ROOT / name
        if path.exists() or path.is_symlink():
            if not stat.S_ISREG(_source_kind(path)):
                raise ValueError(f"Expected source file: {name}")
            files.append(path)
    for name in DIRECTORIES:
        path = ROOT / name
        if path.exists() or path.is_symlink():
            visit(path)
    for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix()):
        name = path.relative_to(ROOT).as_posix()
        _check_source_reference(name)
        yield name, path.read_bytes()


def standalone_page(sources: dict[str, bytes] | None = None):
    # Never reopen a page reference directly: excluded files must stay excluded
    # from the standalone preview just as they do from the source archives.
    if sources is None:
        sources = dict(source_files())

    def source_text(name):
        return _source_bytes(sources, name).decode("utf-8")

    text = source_text("site/index.html")
    css = source_text("site/styles.css")
    js = source_text("site/app.js")
    icon = base64.b64encode(_source_bytes(sources, "site/icon.svg")).decode("ascii")
    text = text.replace('<link rel="stylesheet" href="./styles.css">', "<style>" + css + "</style>")
    text = text.replace('<script src="./app.js" defer></script>', "<script>" + js + "</script>")
    # Defer inline scripts until the DOM exists. There are no remote scripts.
    if "<script>" + js + "</script>" in text:
        text = text.replace("<script>" + js + "</script>", "")
        text = text.replace("</body>", "<script>" + js + "</script>\n</body>")
    text = text.replace('href="./icon.svg"', 'href="data:image/svg+xml;base64,' + icon + '"')
    references = []
    for name in sorted(set(re.findall(r'href="\./docs/([^"]+)"', text))):
        document = source_text("site/docs/" + name)
        anchor = "reference-" + re.sub(r"[^a-zA-Z0-9-]", "-", name)
        text = text.replace('href="./docs/' + name + '"', 'href="#' + anchor + '"')
        references.append('<section class="container" id="' + anchor + '"><details><summary>' +
                          html.escape(name) + '</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' +
                          html.escape(document) + '</pre></details></section>')
    text = text.replace("</main>", "\n".join(references) + "\n</main>")
    return text.encode("utf-8")


def build(output: Path):
    if output.is_symlink():
        raise ValueError("Output directory must not be a symlink")
    try:
        relative_output = output.resolve().relative_to(ROOT)
    except ValueError:
        relative_output = None
    if relative_output is not None and (not relative_output.parts or relative_output.parts[0] in DIRECTORIES):
        raise ValueError("Output must be outside source allowlist directories; use dist")
    output.mkdir(parents=True, exist_ok=True)
    files = list(source_files())
    sources = dict(files)
    match = re.search(r'__version__\s*=\s*[\"\']([^\"\']+)',
                      _source_bytes(sources, "rdc_operator/__init__.py").decode("utf-8"))
    if not match:
        raise ValueError("Version missing")
    version = match.group(1)
    prefix = "RDC-Operator-Kit-" + version
    manifest = {"project": "RDC Operator Kit", "version": version, "files": [
        {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files]}
    files.append(("SOURCE-MANIFEST.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()))
    archive = io.BytesIO()
    with gzip.GzipFile(fileobj=archive, mode="wb", filename="", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for name, data in files:
                info = tarfile.TarInfo(prefix + "/" + name)
                info.size = len(data)
                info.mtime = 0
                info.mode = 0o755 if name.endswith(".sh") else 0o644
                tar.addfile(info, io.BytesIO(data))
    outputs = {prefix + ".tar.gz": archive.getvalue()}
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in files:
            info = zipfile.ZipInfo(prefix + "/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            z.writestr(info, data)
    outputs[prefix + ".zip"] = zipped.getvalue()
    outputs["RDC-Operator-Kit-preview.html"] = standalone_page(sources)
    outputs["SOURCE-MANIFEST.json"] = files[-1][1]
    checksums = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(outputs.items()))
    outputs["SHA256SUMS.txt"] = checksums.encode()
    for name, data in outputs.items():
        target = output / name
        if target.is_symlink():
            raise ValueError(f"Linked output refused: {target}")
        target.write_bytes(data)
    return {"version": version, "source_files": len(files) - 1, "output": str(output.resolve()),
            "artifacts": [{"name": name, "bytes": len(data)} for name, data in outputs.items()]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    print(json.dumps(build(parser.parse_args().output), indent=2))
