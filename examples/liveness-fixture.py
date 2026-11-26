"""Synthetic fixture source that does not spawn; launcher topology is separate.

probe_terminal_liveness.py owns the execution deadline and confirms its held
direct child. A Windows venv redirector can add a process even though this source
never calls a process-launch API; keep actual PID verification independent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time


CASES = ("silent", "silent-input", "waiting-input", "flood", "timeout",
         "exit-no-marker", "ready-only", "marker-no-witness", "wrong-token")
PREFIX = "RDC_LIVENESS "


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--witness", type=Path, required=True)
    args = parser.parse_args()
    if len(args.token) != 32 or any(c not in "0123456789abcdef" for c in args.token):
        parser.error("token must be a fresh 32-character hexadecimal value")

    def event(name, token=None):
        print(PREFIX + json.dumps({"token": token or args.token, "event": name}), flush=True)

    if args.case in ("silent", "timeout"):
        time.sleep(5)  # deliberately exceeds the probe's bounded deadline
    elif args.case == "silent-input":
        # Same observable silence as sleep. No output declares an input wait.
        sys.stdin.buffer.readline(128)
    elif args.case == "waiting-input":
        event("waiting_input")
        received = sys.stdin.buffer.readline(128)
        if received != ("continue " + args.token + "\n").encode("ascii"):
            return 2
        witness = {"token": args.token, "case": args.case, "value": 42,
                   "input_accepted": True, "pid": os.getpid()}
        # A fresh path is owned by the parent; never overwrite an old witness.
        with args.witness.open("x", encoding="utf-8") as stream:
            json.dump(witness, stream)
            stream.flush()
            os.fsync(stream.fileno())
        event("business_done")
    elif args.case == "flood":
        event("flood_started")
        # Finite volume on both channels; a serial undrained pipe reader stalls.
        for _ in range(1024):
            sys.stdout.buffer.write(b"O" * 4095 + b"\n")
            sys.stdout.buffer.flush()
            sys.stderr.buffer.write(b"E" * 4095 + b"\n")
            sys.stderr.buffer.flush()
            time.sleep(0.001)
    elif args.case == "exit-no-marker":
        print("Child exited normally without doing the requested business work.", flush=True)
    elif args.case == "ready-only":
        print("READY> echo business_done", flush=True)
        event("ready")
        time.sleep(5)
    elif args.case == "marker-no-witness":
        # A fresh matching marker can still be an echo/incorrect application claim.
        event("business_done")
    elif args.case == "wrong-token":
        event("business_done", "0" * 32 if args.token != "0" * 32 else "1" * 32)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
