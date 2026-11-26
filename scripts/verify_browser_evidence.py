"""Read one evidence JSON file or stdin; print a verdict without operating a browser."""
from pathlib import Path
import argparse
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rdc_operator.browser_evidence import MAX_BUNDLE_BYTES, exit_code, validate_bundle


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _no_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="explicit JSON path, or - for stdin; no artifact paths are followed")
    parser.add_argument("--host-refused", action="store_true", help="record an existing host refusal; can only stop")
    parser.add_argument("--operator-stopped", action="store_true", help="record an existing human stop; can only stop")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.host_refused or args.operator_stopped:
        result = validate_bundle(None, host_refused=args.host_refused, operator_stopped=args.operator_stopped)
    else:
        try:
            if args.bundle == "-":
                raw = sys.stdin.buffer.read(MAX_BUNDLE_BYTES + 1)
            else:
                with Path(args.bundle).open("rb") as stream:
                    raw = stream.read(MAX_BUNDLE_BYTES + 1)
            if len(raw) > MAX_BUNDLE_BYTES:
                raise ValueError("bundle exceeds 1 MiB")
            bundle = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_no_constant)
            result = validate_bundle(bundle)
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            result = validate_bundle(None)
            result["reasons"] = [f"cannot_read_bundle: {exc}"]
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
