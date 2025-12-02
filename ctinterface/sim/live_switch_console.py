#!/usr/bin/env python3
"""
Interactive switch console that streams synthetic status frames in real time.

Features
- Arbitrary number of boards/channels (defaults to the observed 3-board setup).
- Each board carries address metadata (for reference) and one trailer per 8-slot
  chunk. Addresses come from the DIP switches on the boards; see notes below.
- Console commands let you set a channel to OFF / AUTO / AUTO-ON / HAND and
  change the emit period.
- Outputs frames every cycle (default 300 ms) in the same buslog format as the
  captures; you can pipe the output to a serial adapter if needed.

Optional config file (JSON) to define boards/addresses/trailers:
```
{
  "period_ms": 300,
  "boards": [
    {"name": "Board1", "addr": [53, 150], "base": 1,  "count": 16,
     "trailers": [[89,149,169,149], [169,149,169,90]]},
    {"name": "Board2", "addr": [86, 86],  "base": 17, "count": 16,
     "trailers": [[169,149,170,86], [169,149,170,86]]},
    {"name": "Board3", "addr": [86, 150], "base": 33, "count": 8,
     "trailers": [[165,149,166,86]]}
  ]
}
```
If no config is provided, the defaults above are used.

DIP/address note: Captures show three address pairs on the bus: (0x35,0x96),
(0x56,0x56), (0x56,0x96). The hardware has a 6-bit DIP; we have not fully
decoded how those bits map to the two address bytes. The simulator stores the
addresses for reference but the status frames themselves do not carry them.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

SYNC_HEADER = (0x5C, 0xC7, 0x33)
STATUS_MARKER = (0x35, 0x5A, 0x35)


@dataclass
class BoardConfig:
    name: str
    addr: Tuple[int, int]
    base: int
    count: int
    trailers: List[Tuple[int, int, int, int]]  # one per 8-slot chunk


@dataclass
class Channel:
    number: int
    position: str = "OFF"  # OFF, AUTO, HAND
    auto_on: bool = False


class SwitchConsole:
    def __init__(self, boards: List[BoardConfig], period_ms: int = 300):
        self.period_ms = period_ms
        self.boards = boards
        self._lock = threading.Lock()
        self._record_num = 1
        self._start_ms = int(time.time() * 1000)
        self._stop = threading.Event()
        self._channels: Dict[int, Channel] = {}
        for b in boards:
            for ch in range(b.base, b.base + b.count):
                self._channels[ch] = Channel(number=ch)

    # ----------------------- state helpers -----------------------
    def set_channel(self, ch: int, position: str, auto_on: bool = False) -> None:
        if ch not in self._channels:
            raise ValueError(f"Channel {ch} not configured")
        position = position.upper()
        if position not in {"OFF", "AUTO", "HAND"}:
            raise ValueError("Position must be OFF, AUTO, or HAND")
        with self._lock:
            c = self._channels[ch]
            c.position = position
            c.auto_on = auto_on

    def snapshot(self) -> Dict[int, Channel]:
        with self._lock:
            return {n: Channel(number=c.number, position=c.position, auto_on=c.auto_on) for n, c in self._channels.items()}

    # ----------------------- encoding -----------------------
    @staticmethod
    def _state_to_byte(ch: Channel) -> int:
        if ch.position == "OFF":
            return 0x35
        if ch.position == "HAND":
            return 0xAA
        # AUTO
        return 0x59 if ch.auto_on else 0x65

    def _build_status_frames(self, snapshot: Dict[int, Channel]) -> List[List[int]]:
        frames: List[List[int]] = []
        for board in self.boards:
            variant = 0x35
            for chunk_idx, trailer in enumerate(board.trailers):
                payload = [0x35] * 8
                for offset in range(8):
                    ch_no = board.base + chunk_idx * 8 + offset
                    if ch_no >= board.base + board.count:
                        continue
                    ch = snapshot.get(ch_no)
                    if ch is None:
                        continue
                    byte_val = self._state_to_byte(ch)
                    payload[offset] = byte_val
                    if ch.position == "HAND" or (ch.position == "AUTO" and ch.auto_on):
                        variant = 0x65
                frame = [*SYNC_HEADER, *STATUS_MARKER, variant, *payload, *trailer]
                frames.append(frame)
        return frames

    # ----------------------- output loop -----------------------
    def _buslog_line(self, data: List[int]) -> str:
        ts_ms = self._start_ms + int((self._record_num - 1) * self.period_ms)
        elapsed = (self._record_num - 1) * self.period_ms
        hex_bytes = " ".join(f"{b:02X}" for b in data)
        line = f"[{ts_ms:09d}ms +{elapsed:06d}ms] #{self._record_num:05d} DATA 500k_8E1 {hex_bytes}"
        self._record_num += 1
        return line

    def stream(self) -> None:
        while not self._stop.is_set():
            snap = self.snapshot()
            for frame in self._build_status_frames(snap):
                print(self._buslog_line(frame), flush=True)
            time.sleep(self.period_ms / 1000.0)

    # ----------------------- console -----------------------
    def run_console(self) -> None:
        streamer = threading.Thread(target=self.stream, daemon=True)
        streamer.start()
        print("Live switch console started. Type 'help' for commands.")
        try:
            while True:
                try:
                    line = input("> ").strip()
                except EOFError:
                    break
                if not line:
                    continue
                parts = line.split()
                cmd = parts[0].lower()
                if cmd in {"quit", "exit"}:
                    break
                if cmd == "help":
                    print("Commands: set <ch> off|auto|auto-on|hand | show | period <ms> | quit")
                    continue
                if cmd == "show":
                    snap = self.snapshot()
                    for ch in sorted(snap.keys()):
                        c = snap[ch]
                        status = c.position + ("(ON)" if c.position == "AUTO" and c.auto_on else "")
                        print(f"ch{ch:02d}: {status}")
                    continue
                if cmd == "period" and len(parts) == 2:
                    try:
                        ms = int(parts[1])
                        if ms < 50:
                            print("Period too small; keep >=50ms")
                            continue
                        self.period_ms = ms
                        print(f"Period set to {ms} ms")
                    except ValueError:
                        print("Usage: period <ms>")
                    continue
                if cmd == "set" and len(parts) >= 3:
                    try:
                        ch = int(parts[1])
                    except ValueError:
                        print("Channel must be an integer")
                        continue
                    state = parts[2].lower()
                    try:
                        if state == "off":
                            self.set_channel(ch, "OFF")
                        elif state in {"auto", "auto-idle"}:
                            self.set_channel(ch, "AUTO", auto_on=False)
                        elif state in {"auto-on", "auto_on", "on"}:
                            self.set_channel(ch, "AUTO", auto_on=True)
                        elif state == "hand":
                            self.set_channel(ch, "HAND")
                        else:
                            print("State must be off|auto|auto-on|hand")
                            continue
                    except ValueError as exc:
                        print(exc)
                    continue
                print("Unknown command. Type 'help'.")
        finally:
            self._stop.set()
            streamer.join(timeout=1)


def _default_boards() -> List[BoardConfig]:
    return [
        BoardConfig(
            name="Board1",
            addr=(0x35, 0x96),
            base=1,
            count=16,
            trailers=[(0x59, 0x95, 0xA9, 0x95), (0xA9, 0x95, 0xA9, 0x5A)],
        ),
        BoardConfig(
            name="Board2",
            addr=(0x56, 0x56),
            base=17,
            count=16,
            trailers=[(0xA9, 0x95, 0xAA, 0x56), (0xA9, 0x95, 0xAA, 0x56)],
        ),
        BoardConfig(
            name="Board3",
            addr=(0x56, 0x96),
            base=33,
            count=8,
            trailers=[(0xA5, 0x95, 0xA6, 0x56)],
        ),
    ]


def _load_config(path: Path) -> Tuple[List[BoardConfig], int]:
    data = json.loads(path.read_text())
    period = int(data.get("period_ms", 300))
    boards_json = data.get("boards", [])
    boards: List[BoardConfig] = []
    for b in boards_json:
        boards.append(
            BoardConfig(
                name=b["name"],
                addr=tuple(b["addr"]),
                base=int(b["base"]),
                count=int(b["count"]),
                trailers=[tuple(t) for t in b["trailers"]],
            )
        )
    return boards, period


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Live switch console")
    parser.add_argument("--config", type=Path, help="JSON config describing boards")
    args = parser.parse_args()

    if args.config and args.config.exists():
        boards, period = _load_config(args.config)
    else:
        boards, period = _default_boards(), 300

    console = SwitchConsole(boards=boards, period_ms=period)
    console.run_console()


if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parent))
    main()
