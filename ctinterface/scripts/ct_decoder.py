#!/usr/bin/env python3
"""
CT interface decoder for raw `.log` captures produced by `buslog.py`.

The decoder scans each DATA line for the 0x5C 0xC7 0x33 sync header,
extracts command frames (controller → switchboard) and status frames
(switchboard → controller), and prints a readable timeline that shows the
command intent and the observed switch/relay state bytes.

Usage:
    python ct_decoder.py path/to/capture.log [--limit 40]
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

# Frame markers
SYNC_HEADER = [0x5C, 0xC7, 0x33]
STATUS_HEADER = [0x35, 0x5A, 0x35]
COMMAND_ID = 0xA5

# Board addressing (empirically derived)
BOARD_ADDRESS_MAP: Dict[Tuple[int, int], Dict[str, object]] = {
    (0x35, 0x96): {"label": "Board 1", "channel_range": "ch1-16"},
    (0x56, 0x56): {"label": "Board 2", "channel_range": "ch17-32"},
    (0x56, 0x96): {"label": "Board 3", "channel_range": "ch33-40"},
}

# Channel state lookup
STATE_NAMES = {
    0x35: "OFF",
    0x65: "AUTO_IDLE",
    0x59: "AUTO_ON",
    0x99: "AUTO_ON",
    0x56: "HAND_STEP1",
    0x5A: "HAND_STEP2",
    0x6A: "HAND_STEP3",
    0xAA: "HAND_ON",
}

# Trailer-to-board mapping observed in captures
STATUS_TRAILER_BOARD_MAP: Dict[Tuple[int, int, int, int], str] = {
    (0x59, 0x95, 0xA9, 0x95): "Board 1",
    (0xA9, 0x95, 0xA9, 0x5A): "Board 1",
    (0xA9, 0x95, 0xAA, 0x56): "Board 2",
    (0xA5, 0x95, 0xA6, 0x56): "Board 3",
}


@dataclass
class LogLine:
    timestamp_ms: int
    elapsed_ms: int
    record_num: int
    hex_bytes: List[int]


@dataclass
class CommandFrame:
    raw: List[int]
    board_label: str
    board_range: str
    variant: int
    relay_bytes: List[int]
    trailer: int


@dataclass
class StatusFrame:
    raw: List[int]
    variant: int
    payload: List[int]
    trailer: List[int]
    board_label: str


def parse_log_lines(path: Path) -> Iterator[LogLine]:
    """Yield parsed DATA lines from a `.log` capture."""

    line_re = re.compile(
        r"\[(\d+)ms \+(\d+)ms\]\s+#(\d+)\s+DATA\s+[^\s]+\s+(.+)"
    )

    with path.open("r", encoding="utf-8", errors="ignore") as logfile:
        for line in logfile:
            match = line_re.search(line)
            if not match:
                continue

            timestamp = int(match.group(1))
            elapsed = int(match.group(2))
            record_num = int(match.group(3))
            hex_str = match.group(4).strip()
            if not hex_str:
                continue

            hex_values = [int(token, 16) for token in hex_str.split()]

            yield LogLine(
                timestamp_ms=timestamp,
                elapsed_ms=elapsed,
                record_num=record_num,
                hex_bytes=hex_values,
            )


def chunk_frames(hex_bytes: List[int]) -> Iterator[Tuple[str, List[int]]]:
    """Extract command/status frames from a list of bytes."""

    idx = 0
    length = len(hex_bytes)

    while idx <= length - 3:
        if hex_bytes[idx : idx + 3] != SYNC_HEADER:
            idx += 1
            continue

        # Potential command?
        if (
            idx + 11 <= length
            and hex_bytes[idx + 5] == COMMAND_ID
        ):
            frame = hex_bytes[idx : idx + 11]
            yield ("command", frame)
            idx += 11
            continue

        # Status frame handling (full or truncated)
        if hex_bytes[idx + 3 : idx + 6] == STATUS_HEADER:
            has_room = idx + 19 <= length
            next_sync_within = None

            # Look ahead for an early sync header inside the expected payload/trailer
            search_limit = min(length - idx - 2, 19)
            for offset in range(3, search_limit):
                if hex_bytes[idx + offset : idx + offset + 3] == SYNC_HEADER:
                    next_sync_within = idx + offset
                    break

            if has_room and next_sync_within is None:
                frame = hex_bytes[idx : idx + 19]
                yield ("status", frame)
                idx += 19
            else:
                end_idx = next_sync_within if next_sync_within is not None else length
                frame = hex_bytes[idx:end_idx]
                yield ("status-truncated", frame)
                idx = end_idx
            continue

        # Unknown frame starting with sync
        frame = hex_bytes[idx : min(idx + 12, length)]
        yield ("unknown", frame)
        idx += 1


def decode_command(frame: List[int]) -> CommandFrame:
    """Decode a command frame into human-readable fields."""

    addr = (frame[3], frame[4])
    board_info = BOARD_ADDRESS_MAP.get(addr, {})
    board_label = board_info.get("label", f"addr {frame[3]:02X}{frame[4]:02X}")
    board_range = board_info.get("channel_range", "?")
    variant = frame[6]
    relay_bytes = frame[7:10]
    trailer = frame[10]

    return CommandFrame(
        raw=frame,
        board_label=board_label,
        board_range=str(board_range),
        variant=variant,
        relay_bytes=relay_bytes,
        trailer=trailer,
    )


def decode_status(frame: List[int], board_label: str) -> StatusFrame:
    """Decode a status frame payload."""

    variant = frame[6]
    payload = frame[7:15]
    trailer = frame[15:19]

    return StatusFrame(
        raw=frame,
        variant=variant,
        payload=payload,
        trailer=trailer,
        board_label=board_label,
    )


def format_state(byte_val: int) -> str:
    """Return symbolic state name for a payload byte."""
    name = STATE_NAMES.get(byte_val)
    if name:
        return f"{name}"
    return f"0x{byte_val:02X}"


def process_file(path: Path, limit: Optional[int] = None) -> None:
    """Decode a capture file and print a readable timeline."""

    total_commands = 0
    total_status = 0
    total_truncated = 0
    total_unknown = 0

    previous_states: Dict[Tuple[str, int], int] = {}
    printed = 0

    for logline in parse_log_lines(path):
        for frame_type, frame_bytes in chunk_frames(logline.hex_bytes):
            if limit is not None and printed >= limit:
                break

            prefix = (
                f"[{logline.timestamp_ms:09d}ms +{logline.elapsed_ms:06d}ms] "
                f"#{logline.record_num:05d}"
            )

            if frame_type == "command":
                decoded = decode_command(frame_bytes)
                total_commands += 1

                variant_desc = "activate" if decoded.variant == 0x65 else "poll"
                relay_str = " ".join(f"{b:02X}" for b in decoded.relay_bytes)

                print(
                    f"{prefix} CMD {decoded.board_label} ({decoded.board_range}) "
                    f"variant=0x{decoded.variant:02X} ({variant_desc}) "
                    f"relays={relay_str} trailer={decoded.trailer:02X}"
                )
                printed += 1

            elif frame_type == "status":
                total_status += 1
                decoded = decode_status(frame_bytes, board_label="Unknown")

                board_label = STATUS_TRAILER_BOARD_MAP.get(
                    tuple(decoded.trailer), decoded.board_label
                )

                states = []
                for slot, value in enumerate(decoded.payload):
                    key = (board_label, slot)
                    prev = previous_states.get(key)
                    changed = prev is None or prev != value
                    previous_states[key] = value

                    state_label = format_state(value)
                    slot_label = f"S{slot+1}:{state_label}"
                    if changed:
                        slot_label += "*"
                    states.append(slot_label)

                states_str = ", ".join(states)
                trailer_str = " ".join(f"{b:02X}" for b in decoded.trailer)
                variant_desc = "activate" if decoded.variant == 0x65 else "poll"

                print(
                    f"{prefix} STATUS {board_label} variant=0x{decoded.variant:02X} "
                    f"({variant_desc}) states=[{states_str}] trailer={trailer_str}"
                )
                printed += 1

            elif frame_type == "status-truncated":
                total_truncated += 1
                continue

            else:
                total_unknown += 1
                continue

        if limit is not None and printed >= limit:
            break

    print(
        f"\nSummary: commands={total_commands}, status={total_status}, "
        f"truncated={total_truncated}, unknown={total_unknown}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decode CT interface captures.")
    parser.add_argument(
        "logfile",
        type=Path,
        help="Path to a capture_YYYYMMDD_HHMMSS.log file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the total number of decoded frames printed",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.logfile.exists():
        raise SystemExit(f"File not found: {args.logfile}")
    process_file(args.logfile, limit=args.limit)


if __name__ == "__main__":
    main()
