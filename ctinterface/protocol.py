#!/usr/bin/env python3
"""CT interface protocol helpers.

This module centralizes parsed knowledge from the capture/analysis scripts:

* **Board metadata** (address bytes, channel ranges, checksum trailers).
* **Channel state helpers** (decode HOA position byte to semantic names).
* **Stream decoding** for both `.log` and `.csv` capture formats produced by
  ``buslog.py``.
* **Command frame encoder** that reproduces the controller commands observed
  on the wire for all three boards.

Example usage (see ``__main__`` block for a simple CLI):

>>> from pathlib import Path
>>> from ctinterface import protocol
>>> frames = protocol.iter_frames_from_file(Path("ctinterface/captures/capture_20251111_161616.log"))
>>> first = next(frames)
>>> first.frame_type
'COMMAND'

The decoder yields dataclass instances annotated with board metadata so that
callers can easily correlate payload slots back to switch numbers.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Protocol constants & board metadata
# ---------------------------------------------------------------------------

SYNC_HEADER: Tuple[int, int, int] = (0x5C, 0xC7, 0x33)
STATUS_MARKER: Tuple[int, int, int] = (0x35, 0x5A, 0x35)
COMMAND_ID: int = 0xA5


@dataclass(frozen=True)
class Board:
    """Represents one physical switch board on the CT interface bus."""

    name: str
    addr: Tuple[int, int]
    channel_base: int
    channel_count: int
    relay_idle: Tuple[int, int, int]
    poll_trailer: int
    status_trailers: Tuple[Tuple[int, int, int, int], ...]
    activate_relays: Tuple[int, int, int]


BOARDS: Tuple[Board, ...] = (
    Board(
        name="Board 1",
        addr=(0x35, 0x96),
        channel_base=1,
        channel_count=16,
        relay_idle=(0x9A, 0x35, 0x35),
        poll_trailer=0x6A,
        status_trailers=(
            (0x59, 0x95, 0xA9, 0x95),
            (0xA9, 0x95, 0xA9, 0x5A),
        ),
        activate_relays=(0x9A, 0xAA, 0xAA),
    ),
    Board(
        name="Board 2",
        addr=(0x56, 0x56),
        channel_base=17,
        channel_count=16,
        relay_idle=(0x9A, 0x35, 0x35),
        poll_trailer=0xA6,
        status_trailers=((0xA9, 0x95, 0xAA, 0x56),),
        activate_relays=(0x99, 0x59, 0xAA),  # Observed activation payload
    ),
    Board(
        name="Board 3",
        addr=(0x56, 0x96),
        channel_base=33,
        channel_count=8,
        relay_idle=(0x6A, 0x35, 0x35),
        poll_trailer=0x99,
        status_trailers=((0xA5, 0x95, 0xA6, 0x56),),
        activate_relays=(0x99, 0x35, 0xAA),
    ),
)

BOARD_BY_ADDR: Dict[Tuple[int, int], Board] = {board.addr: board for board in BOARDS}
BOARD_BY_NAME: Dict[str, Board] = {board.name: board for board in BOARDS}

STATUS_TRAILER_TO_BOARD: Dict[Tuple[int, int, int, int], Board] = {}
for board in BOARDS:
    for trailer in board.status_trailers:
        STATUS_TRAILER_TO_BOARD[trailer] = board

TRAILER_SLOT_OFFSET: Dict[Tuple[int, int, int, int], int] = {
    # Board 1 split between two frames
    (0x59, 0x95, 0xA9, 0x95): 0,    # slots 0-7
    (0xA9, 0x95, 0xA9, 0x5A): 8,    # slots 8-15
    # Board 2 (one frame covering slots 0-7, repeated)
    (0xA9, 0x95, 0xAA, 0x56): 0,
    # Board 3 (8 slots)
    (0xA5, 0x95, 0xA6, 0x56): 0,
}


# ---------------------------------------------------------------------------
# Channel state helpers
# ---------------------------------------------------------------------------

# Known state encodings synthesised from protocol analysis docs
STATE_LOOKUP: Dict[int, str] = {
    0x35: "OFF",
    0x65: "AUTO_IDLE",
    0x59: "AUTO_ON",
    0x99: "AUTO_ON",
    0x56: "HAND_STEP1",
    0x5A: "HAND_STEP2",
    0x6A: "HAND_STEP3",
    0xAA: "HAND_ON",
}


def decode_state(byte_value: int) -> str:
    """Return textual state for a single channel byte."""

    return STATE_LOOKUP.get(byte_value, f"0x{byte_value:02X}")


def is_hand_state(byte_value: int) -> bool:
    """True if the byte corresponds to a HAND (manual) action."""

    return byte_value in {0x56, 0x5A, 0x6A, 0xAA}


def is_auto_state(byte_value: int) -> bool:
    """True when controller AUTO authority is active (idle or ON)."""

    return byte_value in {0x65, 0x59, 0x99}


# ---------------------------------------------------------------------------
# Dataclasses describing raw capture records & decoded frames
# ---------------------------------------------------------------------------


@dataclass
class CaptureRecord:
    record_num: int
    timestamp_ms: int
    elapsed_ms: int
    data: List[int]


@dataclass
class Frame:
    record: CaptureRecord
    board: Optional[Board]
    variant: int
    frame_type: str  # "COMMAND" or "STATUS"
    raw: List[int]


@dataclass
class CommandFrame(Frame):
    relay_bytes: Tuple[int, int, int]
    trailer: int


@dataclass
class StatusFrame(Frame):
    payload: List[int]
    trailer: Tuple[int, int, int, int]
    slot_base: int


# ---------------------------------------------------------------------------
# Capture parsing helpers
# ---------------------------------------------------------------------------


LOG_LINE_RE = re.compile(
    r"\[(\d+)ms \+(\d+)ms\]\s+#(\d+)\s+DATA\s+[^\s]+\s+(.+)"
)


def _parse_log(path: Path) -> Iterator[CaptureRecord]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            match = LOG_LINE_RE.search(line)
            if not match:
                continue
            timestamp = int(match.group(1))
            elapsed = int(match.group(2))
            record_num = int(match.group(3))
            payload = match.group(4).strip()
            if not payload:
                continue
            try:
                data = [int(token, 16) for token in payload.split()]
            except ValueError:
                continue
            yield CaptureRecord(record_num, timestamp, elapsed, data)


def _parse_csv(path: Path) -> Iterator[CaptureRecord]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                record_num = int(row["record_num"])
                timestamp = int(row["timestamp_ms"])
                elapsed = int(row.get("elapsed_ms", 0))
            except (KeyError, ValueError):
                continue
            payload = row.get("hex_bytes", "").strip()
            if not payload:
                continue
            try:
                data = [int(token, 16) for token in payload.split()]
            except ValueError:
                continue
            yield CaptureRecord(record_num, timestamp, elapsed, data)


def iter_records(path: Path) -> Iterator[CaptureRecord]:
    """Yield CaptureRecords extracted from either CSV or LOG files."""

    if path.suffix.lower() == ".csv":
        yield from _parse_csv(path)
    else:
        yield from _parse_log(path)


# ---------------------------------------------------------------------------
# Frame decoding
# ---------------------------------------------------------------------------


def _extract_command(record: CaptureRecord, start: int) -> Optional[CommandFrame]:
    data = record.data
    if start + 11 > len(data):
        return None
    frame = data[start : start + 11]
    if frame[5] != COMMAND_ID:
        return None
    board = BOARD_BY_ADDR.get((frame[3], frame[4]))
    return CommandFrame(
        record=record,
        board=board,
        variant=frame[6],
        frame_type="COMMAND",
        raw=frame,
        relay_bytes=(frame[7], frame[8], frame[9]),
        trailer=frame[10],
    )


def _find_next_sync(data: List[int], start: int) -> int:
    """Return the index of the next sync header or len(data) if none."""

    idx = max(start, 0)
    limit = len(data)
    while idx <= limit - 3:
        if tuple(data[idx : idx + 3]) == SYNC_HEADER:
            return idx
        idx += 1
    return limit


def _extract_status(record: CaptureRecord, start: int) -> Optional[StatusFrame]:
    data = record.data
    # Ensure header exists
    if start + 6 >= len(data):
        return None
    if tuple(data[start + 3 : start + 6]) != STATUS_MARKER:
        return None

    variant_index = start + 6
    variant = data[variant_index]
    payload_start = variant_index + 1

    cursor = _find_next_sync(data, payload_start)
    payload_and_trailer = data[payload_start:cursor]
    if len(payload_and_trailer) < 4:
        return None

    trailer = tuple(payload_and_trailer[-4:])
    payload = payload_and_trailer[:-4]
    board = STATUS_TRAILER_TO_BOARD.get(trailer)
    slot_base = TRAILER_SLOT_OFFSET.get(trailer, 0)

    return StatusFrame(
        record=record,
        board=board,
        variant=variant,
        frame_type="STATUS",
        raw=data[start:cursor],
        payload=payload,
        trailer=trailer,
        slot_base=slot_base,
    )


def decode_frames(records: Iterable[CaptureRecord]) -> Iterator[Frame]:
    """Stream decoded frames (command + status) from CaptureRecords."""

    status_cycle = 0
    for record in records:
        idx = 0
        while idx <= len(record.data) - 3:
            if tuple(record.data[idx : idx + 3]) != SYNC_HEADER:
                idx += 1
                continue

            cmd = _extract_command(record, idx)
            if cmd:
                yield cmd
                idx += 11
                continue

            status = _extract_status(record, idx)
            if status:
                if status.board is None and BOARDS:
                    status.board = BOARDS[status_cycle % len(BOARDS)]
                status_cycle += 1
                yield status
                # move index to end of consumed bytes
                idx += len(status.raw)
                continue

            idx += 1


def iter_frames_from_file(path: Path) -> Iterator[Frame]:
    """Convenience helper: decode frames directly from a capture file."""

    return decode_frames(iter_records(path))


# ---------------------------------------------------------------------------
# Command encoder
# ---------------------------------------------------------------------------


def build_command(board: Board, activate: bool) -> bytes:
    """Encode a command frame for a board using observed on-wire patterns."""

    variant = 0x65 if activate else 0x35
    relay_bytes = board.activate_relays if activate else board.relay_idle
    trailer = 0xAA if activate else board.poll_trailer

    frame: List[int] = [
        *SYNC_HEADER,
        board.addr[0],
        board.addr[1],
        COMMAND_ID,
        variant,
        *relay_bytes,
        trailer,
    ]
    return bytes(frame)


def build_command_by_name(board_name: str, activate: bool) -> bytes:
    try:
        board = BOARD_BY_NAME[board_name]
    except KeyError as exc:
        raise ValueError(f"Unknown board: {board_name}") from exc
    return build_command(board, activate)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_status(status: StatusFrame) -> str:
    board_name = status.board.name if status.board else "Unknown"
    # Slots are 0-based because the byte-to-channel mapping is still incomplete.
    start = status.slot_base
    states = ", ".join(
        f"slot{start + idx}:{decode_state(value)}"
        for idx, value in enumerate(status.payload)
    )
    slot_range = f"{start}-{start + len(status.payload) - 1}"
    return (
        f"STATUS {board_name} variant=0x{status.variant:02X} slots[{slot_range}] "
        f"payload=[{states}] trailer={' '.join(f'{b:02X}' for b in status.trailer)}"
    )


def _format_command(cmd: CommandFrame) -> str:
    board_name = cmd.board.name if cmd.board else "Unknown"
    relays = " ".join(f"{b:02X}" for b in cmd.relay_bytes)
    return (
        f"CMD {board_name} variant=0x{cmd.variant:02X} "
        f"relays={relays} trailer={cmd.trailer:02X}"
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Decode CT protocol captures")
    parser.add_argument("capture", type=Path, help="Path to .log or .csv capture")
    parser.add_argument(
        "--limit", type=int, help="Maximum frames to print", default=None
    )
    args = parser.parse_args(argv)

    count = 0
    for frame in iter_frames_from_file(args.capture):
        if isinstance(frame, CommandFrame):
            text = _format_command(frame)
        elif isinstance(frame, StatusFrame):
            text = _format_status(frame)
        else:
            text = f"UNKNOWN frame raw={frame.raw}"
        record = frame.record
        print(
            f"[{record.timestamp_ms:09d}ms +{record.elapsed_ms:06d}ms] "
            f"#{record.record_num:05d} {text}"
        )
        count += 1
        if args.limit is not None and count >= args.limit:
            break


if __name__ == "__main__":
    main()
