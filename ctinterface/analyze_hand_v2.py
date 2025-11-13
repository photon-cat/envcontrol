#!/usr/bin/env python3
"""
Analyze HAND mode test log - Version 2
Focus on Board 1 (channels 1-8) which should be tested systematically.
"""

import re
from collections import defaultdict

def parse_log_file(filename):
    """Parse log file and extract Board 1 frames."""
    frames = []

    with open(filename, 'r') as f:
        for line in f:
            # Extract timestamp and hex bytes
            match = re.search(r'\[(\d+)ms \+(\d+)ms\]\s+#(\d+)\s+DATA\s+500k_8E1\s+(.*)', line)
            if match:
                timestamp = int(match.group(1))
                elapsed = int(match.group(2))
                frame_num = int(match.group(3))
                hex_str = match.group(4)

                # Parse hex bytes
                hex_bytes = hex_str.split()

                # Find Board 1 frames: 5C C7 33 35 5A 35
                i = 0
                while i < len(hex_bytes) - 2:
                    if (i + 2 < len(hex_bytes) and
                        hex_bytes[i] == '5C' and
                        hex_bytes[i+1] == 'C7' and
                        hex_bytes[i+2] == '33'):

                        # Check for Board 1 header
                        if (i + 15 < len(hex_bytes) and
                            hex_bytes[i+3] == '35' and
                            hex_bytes[i+4] == '5A' and
                            hex_bytes[i+5] == '35'):

                            # Extract frame
                            header = hex_bytes[i:i+6]
                            payload = hex_bytes[i+6:i+14]
                            trailer = hex_bytes[i+14:i+16]

                            frames.append({
                                'timestamp': timestamp,
                                'elapsed': elapsed,
                                'frame_num': frame_num,
                                'header': header,
                                'payload': payload,
                                'trailer': trailer
                            })

                            i += 16
                        else:
                            i += 1
                    else:
                        i += 1

    return frames

def analyze_channel_progression(frames):
    """Analyze the sequence of channel activations in HAND mode."""

    print("=== BOARD 1 FRAMES (Channels 1-8) ===\n")
    print(f"{'Frame':>5} {'Elapsed':>8} {'Byte0':>5} {'Byte1':>5} {'Byte2':>5} {'Byte3':>5} {'Byte4':>5} {'Byte5':>5} {'Byte6':>5} {'Byte7':>5} | Notes")
    print("-" * 110)

    baseline = None
    channel_values = {}

    for frame in frames:
        payload = frame['payload']
        payload_str = ' '.join(payload)

        # Convert to hex integers
        payload_bytes = [int(b, 16) for b in payload]

        # Identify baseline (all channels OFF or in AUTO)
        if payload_str == '65 35 35 35 35 35 35 35':
            baseline = payload_bytes
            note = "BASELINE"
        else:
            note = ""

            # Compare to baseline
            if baseline:
                changes = []
                for i in range(8):
                    if payload_bytes[i] != baseline[i]:
                        changes.append(f"B{i}={payload[i]}")

                        # Track this as a channel value
                        # Byte position maps to channel: 0->?, 1->ch1?, etc
                        if i not in channel_values:
                            channel_values[i] = []
                        channel_values[i].append(payload[i])

                if changes:
                    note = "CHANGE: " + ", ".join(changes)

        # Print frame
        print(f"{frame['frame_num']:5d} {frame['elapsed']:8d} ", end='')
        for b in payload:
            print(f"{b:>5}", end=' ')
        print(f"| {note}")

    return channel_values

def decode_hand_values(channel_values):
    """Decode HAND mode byte patterns."""

    print("\n\n=== HAND MODE VALUES BY BYTE POSITION ===\n")

    for pos in sorted(channel_values.keys()):
        values = channel_values[pos]
        unique_vals = list(set(values))
        unique_vals.sort(key=lambda x: int(x, 16))

        print(f"\nByte Position {pos} (Channel {pos+1}?):")
        print(f"  Unique values: {', '.join(unique_vals)}")

        # Decode each unique value
        for val in unique_vals:
            val_int = int(val, 16)
            val_bin = format(val_int, '08b')
            count = values.count(val)
            print(f"    0x{val} = {val_int:3d} = 0b{val_bin} (appears {count} times)")

        # Pattern analysis
        if len(unique_vals) > 1:
            print(f"  Pattern: Multiple values detected - possible state progression or bit combinations")

def analyze_bit_patterns(channel_values):
    """Analyze bit-level patterns in HAND mode values."""

    print("\n\n=== BIT PATTERN ANALYSIS ===\n")

    # Known baseline values:
    # OFF = 0x35 = 0b00110101 = 53
    # AUTO = 0x65 = 0b01100101 = 101

    print("Reference values:")
    print("  OFF  = 0x35 = 0b00110101 = 53")
    print("  AUTO = 0x65 = 0b01100101 = 101")
    print("  Diff = 0x30 = 0b00110000 = 48 (bit 4 and bit 5)")
    print()

    # Analyze each byte position
    for pos in sorted(channel_values.keys()):
        values = channel_values[pos]
        unique_vals = list(set(values))
        unique_vals.sort(key=lambda x: int(x, 16))

        print(f"Byte Position {pos}:")

        for val in unique_vals:
            val_int = int(val, 16)

            # Compare to OFF (0x35)
            diff_off = val_int ^ 0x35
            diff_off_bin = format(diff_off, '08b')

            # Compare to AUTO (0x65)
            diff_auto = val_int ^ 0x65
            diff_auto_bin = format(diff_auto, '08b')

            print(f"  0x{val}:")
            print(f"    XOR with OFF  (0x35): 0x{diff_off:02X} = 0b{diff_off_bin}")
            print(f"    XOR with AUTO (0x65): 0x{diff_auto:02X} = 0b{diff_auto_bin}")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log'

    print("Parsing Board 1 frames...")
    frames = parse_log_file(filename)
    print(f"Found {len(frames)} Board 1 frames\n")

    # Analyze progression
    channel_values = analyze_channel_progression(frames)

    # Decode values
    decode_hand_values(channel_values)

    # Bit pattern analysis
    analyze_bit_patterns(channel_values)

if __name__ == '__main__':
    main()
