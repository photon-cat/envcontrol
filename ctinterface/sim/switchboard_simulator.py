#!/usr/bin/env python3
"""
Switchboard simulator for the CT interface bus.

Goals:
1) Provide a minimal behavioral model of the switch boards so we can replay
   controller command streams and emit status frames that look like the real
   captures.
2) Recreate the two key captures the team has been using for reverse
   engineering:
      - capture_20251111_150227 (HAND sweep across channels)
      - capture_20251111_161616 (AUTO command while switch is in AUTO)

The simulator ingests the original capture's command frames, applies a simple
HOA state machine per channel, and emits status/ack frames that match the
observed patterns. Channel→slot mapping is taken from the HAND capture:
  Board 1: ch1→slot1, ch2→slot0, ch3→slot3, ch4→slot2, ch6→slot4 (auto=0x59)
  Board 2: ch17→slot1, ch18→slot3, ch19→slot2
  Board 3: ch33→slot1, ch34→slot0 (slots2/3 default to 0x99 AUTO_ON baseline)

Unmapped slots stay at OFF (0x35) unless a scenario overrides them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Allow running as a script without installing the package
import sys

sys.path.append(str(Path(__file__).resolve().parent))

from protocol import iter_frames_from_file, CommandFrame

# -----------------------------------------------------------------------------
# Constants and helpers
# -----------------------------------------------------------------------------

SYNC_HEADER = (0x5C, 0xC7, 0x33)
STATUS_MARKER = (0x35, 0x5A, 0x35)
ACK_TRAILER = (0x65, 0x35, 0x35, 0x56)  # Matches the short ack frames in captures
HAND_SEQUENCE = (0x35, 0x56, 0x5A, 0x6A, 0xAA)


class SwitchPosition(Enum):
    OFF = "OFF"
    AUTO = "AUTO"
    HAND = "HAND"


@dataclass
class Channel:
    channel_no: int
    slot: int
    auto_on_code: int = 0x59  # default ON code; some channels override to 0x99
    position: SwitchPosition = SwitchPosition.OFF
    hand_stage: int = 0

    def reset_hand(self) -> None:
        self.hand_stage = 0

    def next_hand_byte(self) -> int:
        # Progress through HAND sequence until latched at 0xAA
        if self.hand_stage < len(HAND_SEQUENCE) - 1:
            self.hand_stage += 1
        return HAND_SEQUENCE[self.hand_stage]


@dataclass
class BoardSim:
    name: str
    trailer: Tuple[int, int, int, int]
    slots: Dict[int, Channel] = field(default_factory=dict)

    def _payload_for_variant(self, activate: bool) -> List[int]:
        payload: List[int] = []
        for slot in range(8):
            ch = self.slots.get(slot)
            if ch is None:
                payload.append(0x35)
                continue

            if ch.position == SwitchPosition.OFF:
                ch.reset_hand()
                payload.append(0x35)
                continue

            if ch.position == SwitchPosition.HAND:
                payload.append(ch.next_hand_byte())
                continue

            # AUTO logic with FET pulse sense:
            # - MCU pulses FET; if sense sees voltage the switch is in AUTO.
            # - When controller commands activate=True the channel drives ON.
            if activate:
                payload.append(ch.auto_on_code)
            else:
                payload.append(0x65)  # AUTO idle
        return payload

    def build_status(self, variant: int, activate: bool) -> List[int]:
        payload = self._payload_for_variant(activate)
        return [
            *SYNC_HEADER,
            *STATUS_MARKER,
            variant,
            *payload,
            *self.trailer,
        ]


# -----------------------------------------------------------------------------
# Scenario event definitions (approximate record numbers from captures)
# -----------------------------------------------------------------------------

# HAND sweep: flip channels to HAND in the observed order (record numbers taken
# from capture_20251111_150227.status records where each slot first changed).
HAND_SWEEP_EVENTS = [
    (8, "Board 1", 1, SwitchPosition.HAND),
    (30, "Board 1", 2, SwitchPosition.HAND),
    (43, "Board 1", 3, SwitchPosition.HAND),
    (59, "Board 1", 4, SwitchPosition.HAND),
    (74, "Board 2", 17, SwitchPosition.HAND),
    (110, "Board 2", 18, SwitchPosition.HAND),
    (123, "Board 2", 19, SwitchPosition.HAND),
    (138, "Board 3", 33, SwitchPosition.HAND),
    (157, "Board 3", 34, SwitchPosition.HAND),
]

# AUTO command test: channel 6 in AUTO, controller commands ON mid-capture.
AUTO_ON_EVENTS = [
    (1, "Board 1", 6, SwitchPosition.AUTO),
]


# -----------------------------------------------------------------------------
# Simulator
# -----------------------------------------------------------------------------


class SwitchboardSimulator:
    def __init__(self) -> None:
        self.boards: Dict[str, BoardSim] = {
            "Board 1": BoardSim(
                name="Board 1",
                trailer=(0xA5, 0xA5, 0xAA, 0x56),
                slots={
                    1: Channel(1, slot=1, auto_on_code=0x99),
                    0: Channel(2, slot=0, auto_on_code=0x59),
                    3: Channel(3, slot=3, auto_on_code=0x99),
                    2: Channel(4, slot=2, auto_on_code=0x99),
                    4: Channel(6, slot=4, auto_on_code=0x59),
                    5: Channel(5, slot=5, auto_on_code=0x59),
                    6: Channel(7, slot=6, auto_on_code=0x59),
                    7: Channel(8, slot=7, auto_on_code=0x59),
                },
            ),
            "Board 2": BoardSim(
                name="Board 2",
                trailer=(0xA5, 0x95, 0xA6, 0x56),
                slots={
                    1: Channel(17, slot=1, auto_on_code=0x59),
                    3: Channel(18, slot=3, auto_on_code=0x59),
                    2: Channel(19, slot=2, auto_on_code=0x59),
                    0: Channel(20, slot=0, auto_on_code=0x59),
                    4: Channel(21, slot=4, auto_on_code=0x59),
                    5: Channel(22, slot=5, auto_on_code=0x59),
                    6: Channel(23, slot=6, auto_on_code=0x59),
                    7: Channel(24, slot=7, auto_on_code=0x59),
                },
            ),
            "Board 3": BoardSim(
                name="Board 3",
                trailer=(0xA5, 0x95, 0xA6, 0x56),
                slots={
                    1: Channel(33, slot=1, auto_on_code=0x59),
                    0: Channel(34, slot=0, auto_on_code=0x59),
                    # Baseline AUTO ON bytes seen in captures for slots 2/3.
                    2: Channel(35, slot=2, auto_on_code=0x99, position=SwitchPosition.AUTO),
                    3: Channel(36, slot=3, auto_on_code=0x99, position=SwitchPosition.AUTO),
                    4: Channel(37, slot=4, auto_on_code=0x59),
                    5: Channel(38, slot=5, auto_on_code=0x59),
                    6: Channel(39, slot=6, auto_on_code=0x59),
                    7: Channel(40, slot=7, auto_on_code=0x59),
                },
            ),
        }

    def apply_event(self, board_name: str, channel_no: int, position: SwitchPosition) -> None:
        board = self.boards[board_name]
        for ch in board.slots.values():
            if ch.channel_no == channel_no:
                ch.position = position
                if position != SwitchPosition.HAND:
                    ch.reset_hand()
                return
        raise ValueError(f"Channel {channel_no} not found on {board_name}")

    def respond_to_command(self, cmd: CommandFrame) -> List[Tuple[int, List[int]]]:
        frames: List[Tuple[int, List[int]]] = []
        board = self.boards[cmd.board.name]
        activate = cmd.variant == 0x65

        # Ack frame when controller is in activation burst.
        if activate:
            frames.append(
                (
                    cmd.record.record_num,
                    [*SYNC_HEADER, *STATUS_MARKER, 0x35, *ACK_TRAILER],
                )
            )

        status_frame = board.build_status(cmd.variant, activate=activate)
        frames.append((cmd.record.record_num, status_frame))
        return frames


# -----------------------------------------------------------------------------
# Capture replay helpers
# -----------------------------------------------------------------------------


def _load_commands(path: Path) -> Iterable[CommandFrame]:
    for frame in iter_frames_from_file(path):
        if isinstance(frame, CommandFrame):
            yield frame


def _format_buslog(record_num: int, timestamp_ms: int, elapsed_ms: int, data: List[int]) -> str:
    hex_bytes = " ".join(f"{b:02X}" for b in data)
    return f"[{timestamp_ms:09d}ms +{elapsed_ms:06d}ms] #{record_num:05d} DATA 500k_8E1 {hex_bytes}"


def replay_capture(capture: Path, scenario: str, out_path: Path) -> None:
    sim = SwitchboardSimulator()
    if scenario == "150227-hand":
        events = HAND_SWEEP_EVENTS
    elif scenario == "161616-auto":
        events = AUTO_ON_EVENTS
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    # Sort events by record number so we can apply them as we stream commands.
    pending_events = list(sorted(events, key=lambda e: e[0]))
    outputs: List[str] = []

    for cmd in _load_commands(capture):
        # Apply any events whose record number has arrived.
        while pending_events and pending_events[0][0] <= cmd.record.record_num:
            _, board_name, ch_no, pos = pending_events.pop(0)
            sim.apply_event(board_name, ch_no, pos)

        outputs.append(_format_buslog(cmd.record.record_num, cmd.record.timestamp_ms, cmd.record.elapsed_ms, cmd.raw))
        for rec, status in sim.respond_to_command(cmd):
            outputs.append(_format_buslog(rec, cmd.record.timestamp_ms, cmd.record.elapsed_ms, status))

    out_path.write_text("\n".join(outputs) + "\n")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate CT switchboard responses")
    parser.add_argument("--capture", required=True, type=Path, help="Path to original capture (log or csv) to replay commands from")
    parser.add_argument("--scenario", required=True, choices=["150227-hand", "161616-auto"], help="Which scenario to simulate")
    parser.add_argument("--out", required=True, type=Path, help="Where to write the simulated log")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    replay_capture(args.capture, args.scenario, args.out)


if __name__ == "__main__":
    main()
