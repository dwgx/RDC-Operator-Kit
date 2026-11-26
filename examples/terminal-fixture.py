"""Small real raw-input TUI with an independent filesystem outcome witness."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--witness", type=Path, required=True)
args = parser.parse_args()
choices = ["Alpha", "Beta", "Gamma"]
selection = 0
previous = None
if os.name == "nt":
    import ctypes
    kernel = ctypes.windll.kernel32
    handle = kernel.GetStdHandle(-10)
    previous = ctypes.c_ulong()
    kernel.GetConsoleMode(handle, ctypes.byref(previous))
    kernel.SetConsoleMode(handle, (previous.value & ~0x0007) | 0x0200)
    import msvcrt
    getch = msvcrt.getwch
else:
    import termios
    import tty
    previous = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    getch = lambda: sys.stdin.read(1)

def draw():
    lines = ["RDC_KIT_MENU", "Use arrows; Enter commits a file witness; q exits.", ""]
    lines += [("> " if i == selection else "  ") + label for i, label in enumerate(choices)]
    sys.stdout.write("\x1b[H\x1b[2J" + "\r\n".join(lines) + "\r\n")
    sys.stdout.flush()

try:
    sys.stdout.write("\x1b[?1049h")
    draw()
    while True:
        char = getch()
        if char in ("q", "\x03", ""):
            break
        if char in ("\r", "\n"):
            args.witness.parent.mkdir(parents=True, exist_ok=True)
            args.witness.write_text(json.dumps({"choice": choices[selection], "index": selection,
                                               "pid": os.getpid()}, ensure_ascii=False), encoding="utf-8")
            break
        if char == "\x1b":
            seq = getch() + getch()
            if seq == "[B":
                selection = (selection + 1) % len(choices)
            elif seq == "[A":
                selection = (selection - 1) % len(choices)
        elif char in ("\x00", "\xe0"):
            code = getch()
            if code == "P": selection = (selection + 1) % len(choices)
            if code == "H": selection = (selection - 1) % len(choices)
        draw()
finally:
    sys.stdout.write("\x1b[?1049l\r\nRDC_KIT_EXIT\r\n")
    sys.stdout.flush()
    if os.name == "nt":
        kernel.SetConsoleMode(handle, previous.value)
    else:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, previous)
