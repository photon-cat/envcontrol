"""High-level tools for decoding and encoding CT2 RS-485 frames."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union
import csv
import re
import string

SYNC_BYTES: Tuple[int, int, int] = (0x5C, 0xC7, 0x33)
STATUS_HEADER: Tuple[int, int, int] = (0x35, 0x5A, 0x35)
COMMAND_MARKER = 0xA5


class Variant(Enum):
    """Command/status variant byte."""

    POLL = 0x35
    ACTIVATE = 0x65

    @classmethod
    def from_byte(cls, value: int) -> "Variant":
        for variant in cls:
            if variant.value == value:
                return variant
        raise ValueError(f"Unsupported variant byte: 0x{value:02X}")


class ChannelState(Enum):
    """Known per-channel state encodings."""

    OFF = 0x35
    AUTO_IDLE = 0x65
    AUTO_ON_A = 0x99
    AUTO_ON_B = 0x59
    HAND_STAGE1 = 0x56
    HAND_STAGE2 = 0x5A
    HAND_STAGE3 = 0x6A
    HAND_ON = 0xAA

    @classmethod
    def from_byte(cls, value: int) -> Optional["ChannelState"]:
        for state in cls:
            if state.value == value:
                return state
        return None


@dataclass(frozen=True)
class BoardDefinition:
    """Static information about each command group/board."""

    board_id: int
    address: Tuple[int, int]
    name: str
    channel_base: int
    poll_pattern: Tuple[int, int, int]
    poll_trailer: int
    activate_pattern: Tuple[int, int, int]
    activate_trailer: int = 0xAA


BOARD_DEFINITIONS: Tuple[BoardDefinition, ...] = (
    BoardDefinition(
        board_id=1,
        address=(0x35, 0x96),
        name="Board 1",
        channel_base=1,
        poll_pattern=(0x9A, 0x35, 0x35),
        poll_trailer=0x6A,
        activate_pattern=(0x9A, 0xAA, 0xAA),
    ),
    BoardDefinition(
        board_id=2,
        address=(0x56, 0x56),
        name="Board 2",
        channel_base=9,
        poll_pattern=(0x9A, 0x35, 0x35),
        poll_trailer=0xA6,
        activate_pattern=(0x99, 0x59, 0xAA),
    ),
    BoardDefinition(
        board_id=3,
        address=(0x56, 0x96),
        name="Board 3",
        channel_base=17,
        poll_pattern=(0x6A, 0x35, 0x35),
        poll_trailer=0x99,
        activate_pattern=(0x99, 0x35, 0xAA),
    ),
)


def _board_by_address(addr: Tuple[int, int]) -> Optional[BoardDefinition]:
    for definition in BOARD_DEFINITIONS:
        if definition.address == addr:
            return definition
    return None


@dataclass
class CommandFrame:
    """Parsed controller → switchboard command."""

    raw: bytes
    board: Optional[BoardDefinition]
    variant: Variant
    relay_bytes: Tuple[int, int, int]
    trailer: int

    @classmethod
    def from_bytes(cls, raw: Sequence[int]) -> "CommandFrame":
        if len(raw) != 11:
            raise ValueError(f"Command frames must be 11 bytes, got {len(raw)}")
        board = _board_by_address((raw[3], raw[4]))
        variant = Variant.from_byte(raw[6])
        relay_bytes = (raw[7], raw[8], raw[9])
        trailer = raw[10]
        return cls(raw=bytes(raw), board=board, variant=variant, relay_bytes=relay_bytes, trailer=trailer)


@dataclass
class StatusFrame:
    """Parsed switchboard → controller status block."""

    raw: bytes
    variant: Variant
    payload: Tuple[int, ...]
    trailer: Tuple[int, ...]

    @property
    def ack_only(self) -> bool:
        return len(self.payload) == 0

    @property
    def channel_states(self) -> Tuple[Optional[ChannelState], ...]:
        return tuple(ChannelState.from_byte(b) for b in self.payload)

    @classmethod
    def from_bytes(cls, raw: Sequence[int]) -> "StatusFrame":
        if len(raw) < 8:
            raise ValueError("Status frames must include header and variant bytes")
        variant = Variant.from_byte(raw[6])
        payload_section = raw[7:]
        if len(payload_section) >= 12:
            payload = tuple(payload_section[:8])
            trailer = tuple(payload_section[8:])
        else:
            payload = tuple()
            trailer = tuple(payload_section)
        return cls(raw=bytes(raw), variant=variant, payload=payload, trailer=trailer)


Frame = Union[CommandFrame, StatusFrame]


class CTInterfaceDecoder:
    """Decode CT interface captures into individual frames."""

    def decode_file(self, path: Union[str, Path]) -> List[Frame]:
        data = _load_capture_bytes(Path(path))
        return self.decode_bytes(data)

    def decode_bytes(self, data: Sequence[int]) -> List[Frame]:
        frames: List[Frame] = []
        i = 0
        length = len(data)
        sync_list = list(SYNC_BYTES)
        status_header = list(STATUS_HEADER)
        while i <= length - 7:
            if data[i : i + 3] == sync_list:
                if i + 5 < length and data[i + 5] == COMMAND_MARKER:
                    if i + 11 > length:
                        break
                    frames.append(CommandFrame.from_bytes(data[i : i + 11]))
                    i += 11
                    continue
                if data[i + 3 : i + 6] == status_header:
                    j = i + 7
                    while j < length and data[j : j + 3] != sync_list:
                        j += 1
                    frames.append(StatusFrame.from_bytes(data[i:j]))
                    i = j
                    continue
            i += 1
        return frames


class CTInterfaceEncoder:
    """Helper for constructing controller command frames."""

    def build_command(
        self,
        board_id: int,
        activate: bool = False,
        relay_override: Optional[Tuple[int, int, int]] = None,
        trailer_override: Optional[int] = None,
    ) -> bytes:
        board = self._board_by_id(board_id)
        variant = Variant.ACTIVATE if activate else Variant.POLL
        if relay_override is not None:
            relay_bytes = relay_override
        else:
            relay_bytes = board.activate_pattern if activate else board.poll_pattern
        trailer = trailer_override if trailer_override is not None else (
            board.activate_trailer if activate else board.poll_trailer
        )
        frame = [*SYNC_BYTES, *board.address, COMMAND_MARKER, variant.value, *relay_bytes, trailer]
        return bytes(frame)

    @staticmethod
    def _board_by_id(board_id: int) -> BoardDefinition:
        for board in BOARD_DEFINITIONS:
            if board.board_id == board_id:
                return board
        raise ValueError(f"Unknown board id {board_id}")


def decode_channel_state(byte_value: int) -> str:
    """Return a human-readable description for a payload byte."""

    state = ChannelState.from_byte(byte_value)
    if state is None:
        return f"UNKNOWN(0x{byte_value:02X})"
    return state.name


def _load_capture_bytes(path: Path) -> List[int]:
    if path.suffix.lower() == ".csv":
        return _load_from_csv(path)
    return _load_from_log(path)


def _load_from_csv(path: Path) -> List[int]:
    data: List[int] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            hex_bytes = row.get("hex_bytes")
            if not hex_bytes:
                continue
            data.extend(int(token, 16) for token in hex_bytes.split())
    return data


_HEX_CHARS = set(string.hexdigits.upper())


def _load_from_log(path: Path) -> List[int]:
    data: List[int] = []
    for line in path.read_text().splitlines():
        match = re.search(r"DATA\s+\S+\s+(.*)", line, re.IGNORECASE)
        if not match:
            continue
        for token in match.group(1).split():
            token = token.upper()
            if len(token) == 2 and set(token) <= _HEX_CHARS:
                data.append(int(token, 16))
    return data


__all__ = [
    "BoardDefinition",
    "ChannelState",
    "CTInterfaceDecoder",
    "CTInterfaceEncoder",
    "CommandFrame",
    "StatusFrame",
    "Variant",
    "decode_channel_state",
]
