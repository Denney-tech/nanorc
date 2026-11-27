#!/usr/bin/env python3
"""Render a file in nano through a pseudo-terminal and report each character's color.

    nano_render.py <nanorc> <file>      # prints the screen, then each run of text with its style
    nano_render.py - <file>             # same, with nano's normal /etc/nanorc + ~/.nanorc

As a module: render(rcfile, path) -> Screen, whose style_of(text) gives the style nano drew
`text` in. nano draws with ncurses, so a small VT100/xterm screen model (cursor moves, erases,
repeats, SGR colors) reconstructs what a terminal would show.
"""
import fcntl
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time
from dataclasses import dataclass

ROWS, COLS = 60, 200


@dataclass(frozen=True)
class Style:
    fg: str = "default"
    bg: str = "default"
    bold: bool = False
    italic: bool = False

    def __str__(self) -> str:
        parts = [f"fg={self.fg}"]
        if self.bg != "default":
            parts.append(f"bg={self.bg}")
        if self.bold:
            parts.append("bold")
        if self.italic:
            parts.append("italic")
        return " ".join(parts)


BASIC = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]


def _apply_sgr(style: Style, params: list) -> Style:
    fg, bg, bold, italic = style.fg, style.bg, style.bold, style.italic
    i = 0
    if not params:
        params = [0]
    while i < len(params):
        p = params[i]
        if p == 0:
            fg, bg, bold, italic = "default", "default", False, False
        elif p == 1:
            bold = True
        elif p == 3:
            italic = True
        elif p in (22,):
            bold = False
        elif p == 23:
            italic = False
        elif 30 <= p <= 37:
            fg = BASIC[p - 30]
        elif 90 <= p <= 97:
            fg = "light" + BASIC[p - 90]
        elif p == 39:
            fg = "default"
        elif 40 <= p <= 47:
            bg = BASIC[p - 40]
        elif 100 <= p <= 107:
            bg = "light" + BASIC[p - 100]
        elif p == 49:
            bg = "default"
        elif p in (38, 48) and i + 2 < len(params) and params[i + 1] == 5:
            value = f"c{params[i + 2]}"
            if p == 38:
                fg = value
            else:
                bg = value
            i += 2
        i += 1
    return Style(fg, bg, bold, italic)


class Screen:
    def __init__(self):
        self.cells = [[(" ", Style()) for _ in range(COLS)] for _ in range(ROWS)]
        self.row = self.col = 0
        self.style = Style()
        self.last_char = " "

    def _put(self, ch: str):
        if self.col >= COLS:
            self.col = 0
            self.row = min(self.row + 1, ROWS - 1)
        self.cells[self.row][self.col] = (ch, self.style)
        self.last_char = ch
        self.col += 1

    def feed(self, data: str):
        i = 0
        csi = re.compile(r"\x1b\[([?>]?)([0-9;]*)([@-~])")
        while i < len(data):
            ch = data[i]
            if ch == "\x1b":
                m = csi.match(data, i)
                if m:
                    self._csi(m.group(1), m.group(2), m.group(3))
                    i = m.end()
                    continue
                # ESC ( B, ESC ) 0, ESC =, ESC >, ESC 7/8, OSC ... BEL
                if data.startswith("\x1b]", i):
                    end = data.find("\x07", i)
                    i = len(data) if end < 0 else end + 1
                    continue
                i += 3 if i + 1 < len(data) and data[i + 1] in "()" else 2
                continue
            if ch == "\r":
                self.col = 0
            elif ch == "\n":
                self.row = min(self.row + 1, ROWS - 1)
            elif ch == "\b":
                self.col = max(self.col - 1, 0)
            elif ch == "\t":
                self.col = min((self.col // 8 + 1) * 8, COLS - 1)
            elif ch >= " ":
                self._put(ch)
            i += 1

    def _csi(self, private: str, raw: str, final: str):
        if private:
            return  # mode set/reset (?1049h etc.)
        nums = [int(x) if x else 0 for x in raw.split(";")] if raw else []

        def n(default=1):
            return nums[0] if nums and nums[0] else default

        if final == "m":
            self.style = _apply_sgr(self.style, nums)
        elif final in "Hf":
            self.row = (nums[0] if len(nums) > 0 and nums[0] else 1) - 1
            self.col = (nums[1] if len(nums) > 1 and nums[1] else 1) - 1
        elif final == "A":
            self.row = max(self.row - n(), 0)
        elif final == "B":
            self.row = min(self.row + n(), ROWS - 1)
        elif final == "C":
            self.col = min(self.col + n(), COLS - 1)
        elif final == "D":
            self.col = max(self.col - n(), 0)
        elif final == "G":
            self.col = n() - 1
        elif final == "d":
            self.row = n() - 1
        elif final == "K":
            mode = nums[0] if nums else 0
            rng = range(self.col, COLS) if mode == 0 else range(0, self.col + 1) if mode == 1 else range(COLS)
            for c in rng:
                self.cells[self.row][c] = (" ", self.style)
        elif final == "J":
            mode = nums[0] if nums else 0
            rows = range(self.row + 1, ROWS) if mode == 0 else range(ROWS) if mode == 2 else range(0, self.row)
            if mode == 0:
                for c in range(self.col, COLS):
                    self.cells[self.row][c] = (" ", self.style)
            for r in rows:
                self.cells[r] = [(" ", self.style) for _ in range(COLS)]
        elif final == "X":
            for c in range(self.col, min(self.col + n(), COLS)):
                self.cells[self.row][c] = (" ", self.style)
        elif final == "b":
            for _ in range(n()):
                self._put(self.last_char)
        elif final == "@":
            line = self.cells[self.row]
            for _ in range(n()):
                line.insert(self.col, (" ", self.style))
                line.pop()
        elif final == "P":
            line = self.cells[self.row]
            for _ in range(n()):
                line.pop(self.col)
                line.append((" ", self.style))
        elif final == "L":
            for _ in range(n()):
                self.cells.insert(self.row, [(" ", self.style) for _ in range(COLS)])
                self.cells.pop()
        elif final == "M":
            for _ in range(n()):
                self.cells.pop(self.row)
                self.cells.append([(" ", self.style) for _ in range(COLS)])

    # --- queries -------------------------------------------------------------------------
    def text_lines(self) -> list:
        return ["".join(ch for ch, _ in row).rstrip() for row in self.cells]

    def find(self, text: str, occurrence: int = 1):
        """(row, col) of the n-th occurrence of `text` in the editing area (not the title bar
        or the help lines at the bottom)."""
        seen = 0
        for r, line in enumerate(self.text_lines()):
            if r == 0 or r >= ROWS - 3:
                continue
            start = 0
            while (c := line.find(text, start)) >= 0:
                seen += 1
                if seen == occurrence:
                    return r, c
                start = c + 1
        raise LookupError(f"{text!r} not on screen")

    def style_of(self, text: str, occurrence: int = 1, within: str = None) -> Style:
        """Style nano drew `text` in; raises if its characters are not all the same style.
        With `within`, `text` is looked up inside the n-th occurrence of that longer context."""
        if within is not None:
            if text not in within:
                raise ValueError(f"{text!r} is not part of {within!r}")
            r, c = self.find(within, occurrence)
            c += within.index(text)
        else:
            r, c = self.find(text, occurrence)
        styles = {self.cells[r][c + k][1] for k in range(len(text)) if not text[k].isspace()}
        if len(styles) != 1:
            raise AssertionError(f"{text!r} is drawn in mixed styles: {', '.join(map(str, styles))}")
        return styles.pop()

    def runs(self):
        """(row, text, style) for each run of same-styled text."""
        for r, row in enumerate(self.cells):
            run, style = "", None
            for ch, st in row:
                if st != style and run.strip():
                    yield r, run, style
                    run = ""
                elif st != style:
                    run = ""
                style = st
                run += ch
            if run.strip():
                yield r, run.rstrip(), style


def render(rcfile, path: str, settle: float = 1.0, timeout: float = 20.0) -> Screen:
    """Open `path` in nano using only `rcfile` (or, with rcfile None, nano's normal
    /etc/nanorc + ~/.nanorc), capture the drawn screen, then quit."""
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
        os.environ["TERM"] = "xterm-256color"
        os.environ.pop("NO_COLOR", None)
        rc_args = ["--rcfile", rcfile] if rcfile else []
        os.execvp("nano", ["nano", *rc_args, "--view", path])
    screen = Screen()
    raw = bytearray()
    deadline = time.monotonic() + timeout
    last_data = time.monotonic()
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            raw += data
            last_data = time.monotonic()
        elif raw and time.monotonic() - last_data > settle:
            break
    try:
        os.write(fd, b"\x18")  # ^X: exit (view mode: never asks to save)
        time.sleep(0.2)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except (OSError, ChildProcessError):
        pass
    screen.feed(raw.decode("utf-8", "replace"))
    screen.raw = bytes(raw)
    return screen


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    screen = render(None if sys.argv[1] == "-" else sys.argv[1], sys.argv[2])
    for line in screen.text_lines():
        if line:
            print(line)
    print("--- styled runs (default style omitted):")
    for r, text, style in screen.runs():
        if style != Style():
            print(f"{r:3} {style!s:28} {text.strip()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
