from collections import Counter
from pathlib import Path

from ..protocol import (
    CTInterfaceDecoder,
    CTInterfaceEncoder,
    ChannelState,
    CommandFrame,
    StatusFrame,
    Variant,
)

CAPTURE = Path(__file__).resolve().parents[1] / "capture_20251111_145830.csv"


def test_decoder_counts_frames():
    decoder = CTInterfaceDecoder()
    frames = decoder.decode_file(CAPTURE)
    commands = [f for f in frames if isinstance(f, CommandFrame)]
    statuses = [f for f in frames if isinstance(f, StatusFrame)]

    assert len(commands) == 615

    board_counts = Counter((cmd.board.board_id if cmd.board else None) for cmd in commands)
    assert board_counts[1] == 199
    assert board_counts[2] == 199
    assert board_counts[3] == 217

    channel_statuses = [s for s in statuses if not s.ack_only]
    ack_statuses = [s for s in statuses if s.ack_only]
    assert len(channel_statuses) == 465
    assert len(ack_statuses) == 120


def test_first_frames_match_reference():
    decoder = CTInterfaceDecoder()
    frames = decoder.decode_file(CAPTURE)
    first_cmd = next(f for f in frames if isinstance(f, CommandFrame))
    assert first_cmd.variant == Variant.POLL
    assert first_cmd.raw == bytes.fromhex("5C C7 33 35 96 A5 35 9A 35 35 6A")

    first_status = next(f for f in frames if getattr(f, "payload", ()) == tuple([0x35] * 8))
    assert all(state == ChannelState.OFF for state in first_status.channel_states)


def test_encoder_matches_observed_frames():
    encoder = CTInterfaceEncoder()
    board1_poll = encoder.build_command(board_id=1, activate=False)
    assert board1_poll == bytes.fromhex("5C C7 33 35 96 A5 35 9A 35 35 6A")

    board2_activate = encoder.build_command(board_id=2, activate=True)
    assert board2_activate == bytes.fromhex("5C C7 33 56 56 A5 65 99 59 AA AA")

    board3_activate = encoder.build_command(board_id=3, activate=True)
    assert board3_activate == bytes.fromhex("5C C7 33 56 96 A5 65 99 35 AA AA")
