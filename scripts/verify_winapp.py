"""Verify the official archive and every installed byte before execution."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reject_link(path):
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("Link or junction refused: " + path.name)


def verify_install(archive: Path, expected: str, destination: Path):
    # Content verification is not a sandbox against a hostile OS account.
    for path in (archive, destination, *destination.parents):
        reject_link(path)
    if sha_file(archive) != expected.lower():
        raise ValueError("Archive SHA-256 mismatch")
    manifest = {}
    with zipfile.ZipFile(archive) as package:
        total = 0
        for item in package.infolist():
            rel = PurePosixPath(item.filename)
            if (rel.is_absolute() or ".." in rel.parts or "\\" in item.filename
                    or ":" in item.filename or not rel.parts or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("Unsafe archive entry")
            if item.is_dir():
                continue
            total += item.file_size
            if total > 1024 * 1024 * 1024 or item.file_size > 512 * 1024 * 1024:
                raise ValueError("Archive exceeds extraction budget")
            if item.filename.casefold() in {name.casefold() for name in manifest}:
                raise ValueError("Ambiguous archive names")
            with package.open(item) as source:
                digest = hashlib.sha256()
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            manifest[item.filename] = digest.hexdigest()
        if "winapp.exe" not in manifest:
            raise ValueError("Unexpected archive layout")
        if destination.exists():
            actual = {}
            for path in destination.rglob("*"):
                reject_link(path)
                if path.is_file():
                    actual[path.relative_to(destination).as_posix()] = sha_file(path)
            if actual != manifest:
                raise ValueError("Existing winapp directory differs from the verified archive; preserved without execution")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix="winapp-staging-", dir=destination.parent))
            try:
                package.extractall(staging)
                staging.rename(destination)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    return {"archive_sha256": expected.lower(), "verified_files": len(manifest)}


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_install(args.archive, args.sha256, args.destination)))
