#!/usr/bin/env python3
"""
Final HAND mode analysis - identify the exact byte values for each channel.

Based on manual observation of the log, the pattern appears to be:
- Channels are toggled one at a time to HAND mode (ON)
- The test starts around frame 8 (elapsed ~1805ms) with Channel 1
- Channel progression visible in byte position 2 (B2), then B1+B2, then B1+B2+B3, etc.
"""

import re

def parse_board1_frames(filename):
    """Parse Board 1 frames."""
    frames = []

    with open(filename, 'r') as f:
        for line in f:
            match = re.search(r'\[(\d+)ms \+(\d+)ms\]\s+#(\d+)\s+DATA\s+500k_8E1\s+(.*)', line)
            if match:
                timestamp = int(match.group(1))
                elapsed = int(match.group(2))
                frame_num = int(match.group(3))
                hex_str = match.group(4)
                hex_bytes = hex_str.split()

                # Find Board 1 frames: 5C C7 33 35 5A 35
                i = 0
                while i < len(hex_bytes) - 2:
                    if (i + 2 < len(hex_bytes) and
                        hex_bytes[i] == '5C' and
                        hex_bytes[i+1] == 'C7' and
                        hex_bytes[i+2] == '33' and
                        i + 15 < len(hex_bytes) and
                        hex_bytes[i+3] == '35' and
                        hex_bytes[i+4] == '5A' and
                        hex_bytes[i+5] == '35'):

                        payload = hex_bytes[i+6:i+14]
                        frames.append({
                            'timestamp': timestamp,
                            'elapsed': elapsed,
                            'frame_num': frame_num,
                            'payload': payload,
                            'payload_hex': [int(b, 16) for b in payload]
                        })
                        i += 16
                    else:
                        i += 1

    return frames

def extract_hand_patterns(frames):
    """Extract HAND mode patterns by analyzing the progression."""

    baseline = [0x65, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35]

    print("=== HAND MODE TEST SEQUENCE ===\n")
    print("Looking for progression of channel activations...\n")

    # Track unique non-baseline payloads
    seen_payloads = set()
    transitions = []

    for i, frame in enumerate(frames):
        payload = frame['payload_hex']
        payload_str = ' '.join(frame['payload'])

        # Skip baseline frames
        if payload == baseline:
            continue

        # Skip duplicate sequential payloads
        if payload_str in seen_payloads:
            continue

        seen_payloads.add(payload_str)

        # Identify what changed
        changes = []
        for pos in range(8):
            if payload[pos] != baseline[pos]:
                changes.append(f"B{pos}=0x{payload[pos]:02X}")

        transitions.append({
            'frame': frame['frame_num'],
            'elapsed': frame['elapsed'],
            'payload': payload,
            'payload_str': payload_str,
            'changes': changes
        })

    # Print transitions
    print(f"{'Frame':>5} {'Elapsed':>8} | {'B0':>5} {'B1':>5} {'B2':>5} {'B3':>5} {'B4':>5} {'B5':>5} {'B6':>5} {'B7':>5} | Changes")
    print("-" * 110)

    for trans in transitions:
        print(f"{trans['frame']:5d} {trans['elapsed']:8d} | ", end='')
        for b in trans['payload']:
            print(f"{b:5X}", end=' ')
        print(f"| {', '.join(trans['changes'])}")

    return transitions

def identify_channels(transitions):
    """Identify which channel each transition represents."""

    print("\n\n=== CHANNEL IDENTIFICATION ===\n")

    # Manual analysis based on observed patterns:
    # Channel 1: B2 changes from 35 -> 56 -> 5A -> 6A -> AA
    # Channel 2: B1 changes from 35 -> 56 -> 5A -> 6A -> AA (while B2=AA)
    # Channel 3: B3 changes from 35 -> 56 -> 5A -> 6A -> AA (while B1=AA, B2=AA)
    # etc.

    # Look for the "progressive AA" pattern
    channel_map = {}
    channel_num = 0

    prev_aa_count = 0

    for trans in transitions:
        payload = trans['payload']

        # Count how many bytes are 0xAA
        aa_count = payload.count(0xAA)

        # Count how many bytes are in HAND mode (not 0x35, 0x65, 0x99)
        hand_bytes = []
        for i, b in enumerate(payload):
            if b not in [0x35, 0x65, 0x99]:
                hand_bytes.append((i, b))

        # When AA count increases, we've moved to a new channel
        if aa_count > prev_aa_count:
            channel_num += 1

        # The "active" channel is the one with non-AA HAND value
        active_byte = None
        for i, b in hand_bytes:
            if b != 0xAA:
                active_byte = (i, b)
                break

        if active_byte is None and len(hand_bytes) > 0:
            # All are AA, use the last one
            active_byte = hand_bytes[-1]

        if active_byte:
            pos, val = active_byte
            if channel_num not in channel_map:
                channel_map[channel_num] = []

            channel_map[channel_num].append({
                'byte_pos': pos,
                'value': val,
                'value_hex': f"0x{val:02X}",
                'value_bin': f"0b{val:08b}",
                'frame': trans['frame'],
                'elapsed': trans['elapsed']
            })

        prev_aa_count = aa_count

    return channel_map

def print_channel_summary(channel_map):
    """Print summary of channel encodings."""

    print("\n\n=== CHANNEL ENCODING SUMMARY ===\n")

    for ch in sorted(channel_map.keys()):
        entries = channel_map[ch]
        byte_positions = list(set(e['byte_pos'] for e in entries))
        values = list(set(e['value'] for e in entries))
        values.sort()

        print(f"Channel {ch}:")
        print(f"  Byte position: {byte_positions[0]}")
        print(f"  HAND mode values:")
        for val in values:
            print(f"    0x{val:02X} = {val:3d} = 0b{val:08b}")
        print()

def analyze_value_progression():
    """Analyze the progression of HAND mode values."""

    print("\n=== VALUE PROGRESSION ANALYSIS ===\n")

    print("Observed HAND mode value sequences:")
    print("  35 (OFF) -> 56 -> 5A -> 6A -> AA (HAND ON)")
    print()

    values = [0x35, 0x56, 0x5A, 0x6A, 0xAA]
    print("Binary patterns:")
    for val in values:
        print(f"  0x{val:02X} = 0b{val:08b}")

    print("\nBit differences (XOR with previous value):")
    for i in range(1, len(values)):
        diff = values[i] ^ values[i-1]
        print(f"  0x{values[i-1]:02X} -> 0x{values[i]:02X}: XOR = 0x{diff:02X} = 0b{diff:08b}")

    print("\nKey findings:")
    print("  - OFF  = 0x35 = 0b00110101")
    print("  - HAND = 0xAA = 0b10101010")
    print("  - Transition values (56, 5A, 6A) are intermediate states")
    print("  - 0xAA = fully ON in HAND mode")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log'

    print("Parsing log file...")
    frames = parse_board1_frames(filename)
    print(f"Found {len(frames)} Board 1 frames\n")

    # Extract patterns
    transitions = extract_hand_patterns(frames)

    # Identify channels
    channel_map = identify_channels(transitions)

    # Print summary
    print_channel_summary(channel_map)

    # Analyze progression
    analyze_value_progression()

if __name__ == '__main__':
    main()
