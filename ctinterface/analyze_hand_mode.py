#!/usr/bin/env python3
"""
Analyze HAND mode test log to extract byte patterns for each channel.
"""

import re
from collections import defaultdict

def parse_log_file(filename):
    """Parse log file and extract all valid frames."""
    frames = []

    with open(filename, 'r') as f:
        for line in f:
            # Extract hex bytes from the line
            # Format: [timestamp] #frame DATA 500k_8E1 <hex bytes>
            match = re.search(r'#(\d+)\s+DATA\s+500k_8E1\s+(.*)', line)
            if match:
                frame_num = int(match.group(1))
                hex_str = match.group(2)

                # Parse all hex bytes
                hex_bytes = hex_str.split()

                # Find all complete frames starting with 5C C7 33
                i = 0
                while i < len(hex_bytes) - 2:
                    if (i + 2 < len(hex_bytes) and
                        hex_bytes[i] == '5C' and
                        hex_bytes[i+1] == 'C7' and
                        hex_bytes[i+2] == '33'):

                        # Need at least 16 bytes for complete frame
                        if i + 16 <= len(hex_bytes):
                            frame_data = hex_bytes[i:i+16]

                            # Check for standard frame structure: 5C C7 33 35 5A 35
                            # OR variant: 5C C7 33 56 5A 35 (board indicator changes)
                            if (len(frame_data) >= 6 and
                                frame_data[3] in ['35', '56'] and
                                frame_data[4] in ['5A', '96'] and
                                frame_data[5] in ['35', 'A5']):

                                # This is a valid frame
                                # Structure: [header 6 bytes] [payload 8 bytes] [trailer 2 bytes]
                                header = frame_data[0:6]
                                payload = frame_data[6:14]
                                trailer = frame_data[14:16]

                                frames.append({
                                    'frame_num': frame_num,
                                    'header': header,
                                    'payload': payload,
                                    'trailer': trailer,
                                    'full': frame_data
                                })
                                i += 16
                            else:
                                i += 1
                        else:
                            i += 1
                    else:
                        i += 1

    return frames

def group_frames_by_board(frames):
    """Group frames by board based on payload patterns."""
    # We expect board cycles: board1, board2, board3, board4, board5, repeat
    boards = {1: [], 2: [], 3: [], 4: [], 5: []}

    # Track baseline patterns to identify boards
    for frame in frames:
        payload = ' '.join(frame['payload'])

        # Identify board by characteristic patterns
        # Board 1: starts with 65 35
        # Board 2: starts with 65 35 35 99
        # Board 3: (need to identify)
        # etc

        # For now, collect all unique payloads
        boards[payload] = frame

    return boards

def analyze_hand_patterns(frames):
    """Analyze frames to identify HAND mode byte patterns."""

    # Separate frames into baseline and HAND-active
    baseline_frames = []
    hand_frames = []

    for frame in frames:
        payload_str = ' '.join(frame['payload'])

        # Baseline: all 35 (OFF state for most channels)
        if payload_str == '65 35 35 35 35 35 35 35':
            baseline_frames.append(frame)
        # HAND mode frames: contains AA or other non-35, non-65, non-99 patterns
        elif 'AA' in payload_str or '56' in payload_str or '5A' in payload_str or '6A' in payload_str:
            hand_frames.append(frame)

    return baseline_frames, hand_frames

def extract_channel_changes(frames):
    """Track payload changes across frames to identify which channels are being toggled."""

    # Track payloads across time
    payload_sequence = []

    for frame in frames:
        payload_hex = [int(b, 16) for b in frame['payload']]
        payload_sequence.append({
            'frame': frame['frame_num'],
            'payload': payload_hex,
            'payload_str': ' '.join(frame['payload'])
        })

    # Find transitions where a single byte changes from baseline
    baseline = [0x65, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35]  # Board 1 baseline

    transitions = []
    prev_payload = baseline

    for entry in payload_sequence:
        curr_payload = entry['payload']

        # Find which positions changed
        changes = []
        for i in range(8):
            if curr_payload[i] != baseline[i]:
                changes.append((i, curr_payload[i]))

        if len(changes) > 0:
            transitions.append({
                'frame': entry['frame'],
                'payload': curr_payload,
                'payload_str': entry['payload_str'],
                'changes': changes
            })

        prev_payload = curr_payload

    return transitions

def build_channel_mapping(frames):
    """Build mapping of channel number to HAND mode byte values."""

    # Expected sequence: channels 1-40 toggled one at a time
    # Each board has 8 channels, 5 boards total

    channel_map = {}

    # Look for frames with HAND mode indicators
    for frame in frames:
        payload = frame['payload']
        payload_str = ' '.join(payload)

        # Skip baseline frames
        if payload_str == '65 35 35 35 35 35 35 35':
            continue

        # Check each byte position for HAND mode values
        for pos in range(8):
            byte_val = payload[pos]

            # HAND mode candidates: not 35 (OFF), not 65 (AUTO high bit)
            if byte_val not in ['35', '65', '99', '56']:  # 56 might be trailer
                # This is likely a HAND mode value
                if byte_val not in ['5C', 'C7', '33', '5A', 'A5', 'A9', 'A6']:  # Filter header/trailer
                    print(f"Frame {frame['frame_num']}, Position {pos}, Byte: {byte_val}, Full: {payload_str}")

    return channel_map

def analyze_by_board_cycle(frames):
    """Analyze frames in board cycles to identify individual channel changes."""

    # Group frames that appear to be from the same board
    # Typically we see a repeating pattern of 5 boards

    print("\\n=== ANALYZING BY BOARD POSITION ===\\n")

    # Look for the pattern of HAND mode activation
    # Format: 65 [byte1] [byte2] [byte3] [byte4] [byte5] [byte6] [byte7]

    hand_mode_values = defaultdict(list)

    for frame in frames:
        payload = frame['payload']

        # Check if this is a HAND mode frame (contains AA or other non-standard values)
        if 'AA' in payload or '5A' in payload or '6A' in payload:
            payload_str = ' '.join(payload)
            print(f"Frame {frame['frame_num']:4d}: {payload_str}")

            # Record which positions have non-standard values
            for pos in range(8):
                byte_val = payload[pos]
                if byte_val not in ['35', '65', '99', '56', '5C', 'C7', '33', '5A']:
                    hand_mode_values[pos].append((frame['frame_num'], byte_val))

    print("\\n=== HAND MODE VALUES BY POSITION ===\\n")
    for pos in sorted(hand_mode_values.keys()):
        print(f"Position {pos}:")
        for frame_num, byte_val in hand_mode_values[pos][:10]:  # Show first 10
            print(f"  Frame {frame_num:4d}: 0x{byte_val} ({int(byte_val, 16):3d}, 0b{int(byte_val, 16):08b})")

    return hand_mode_values

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log'

    print("Parsing log file...")
    frames = parse_log_file(filename)
    print(f"Found {len(frames)} valid frames\\n")

    # Show first few frames
    print("=== FIRST 10 FRAMES ===\\n")
    for frame in frames[:10]:
        print(f"Frame {frame['frame_num']:4d}: {' '.join(frame['payload'])}")

    print("\\n=== ANALYZING HAND MODE PATTERNS ===\\n")

    # Analyze board cycles
    hand_mode_values = analyze_by_board_cycle(frames)

    # Statistical analysis
    print("\\n=== SUMMARY ===\\n")
    print(f"Total frames analyzed: {len(frames)}")

    # Count unique payloads
    unique_payloads = set()
    for frame in frames:
        unique_payloads.add(' '.join(frame['payload']))
    print(f"Unique payload patterns: {len(unique_payloads)}")

    # Find all unique byte values in HAND mode positions
    hand_bytes = set()
    for frame in frames:
        for byte_val in frame['payload']:
            if byte_val not in ['35', '65', '99']:
                hand_bytes.add(byte_val)

    print(f"\\nUnique byte values (excluding 35, 65, 99):")
    for byte_val in sorted(hand_bytes):
        print(f"  0x{byte_val} ({int(byte_val, 16):3d}, 0b{int(byte_val, 16):08b})")

if __name__ == '__main__':
    main()
