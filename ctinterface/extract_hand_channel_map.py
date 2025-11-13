#!/usr/bin/env python3
"""
Extract exact channel-to-byte mappings from HAND mode test.
"""

import re

def parse_board1_frames(filename):
    """Parse Board 1 frames with timestamps."""
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
                            'payload': payload
                        })
                        i += 16
                    else:
                        i += 1

    return frames

def identify_channel_sequence(frames):
    """Identify which channels are toggled in sequence."""

    baseline = [0x65, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35]

    # Track transitions
    channel_map = {}
    last_change_pos = None
    channel_num = 0

    print("=== CHANNEL ACTIVATION SEQUENCE ===\n")
    print(f"{'Time':>8} {'Ch':>3} {'Byte':>4} {'Value':>6} | Payload")
    print("-" * 70)

    for frame in frames:
        payload = [int(b, 16) for b in frame['payload']]
        payload_str = ' '.join(frame['payload'])

        # Detect which byte positions changed
        changes = []
        for i in range(8):
            if payload[i] != baseline[i]:
                changes.append((i, payload[i]))

        # Look for single-channel activations (HAND mode markers)
        # Pattern: byte positions 1 and 2 both show non-baseline values
        if len(changes) >= 2:
            # Check if we have AA AA pattern (HAND mode active)
            if 'AA' in frame['payload']:
                # Count how many bytes are AA
                aa_positions = [i for i, b in enumerate(frame['payload']) if b == 'AA']

                # Pattern analysis:
                # Early: B2=56, B2=5A, B2=6A, B2=AA (channel 1)
                # Later: B1=56/5A/6A/AA, B2=AA (channel 2)
                # Later: B1=AA, B2=AA, B3=56/5A/6A/AA (channel 3)
                # etc.

                # Identify the "active" position (the one changing)
                if len(aa_positions) >= 2:
                    # Multiple AA bytes - identify which channel
                    # B1=AA, B2=AA means channel boundary

                    # Look for the position with variety (not just AA)
                    active_pos = None
                    active_val = None

                    for pos, val in changes:
                        if val != 0x65 and val != 0x35:  # Not baseline
                            if val != 0xAA:  # Not full ON yet
                                active_pos = pos
                                active_val = val
                            elif pos not in [1, 2] or len(aa_positions) > 2:
                                # AA in later positions
                                active_pos = pos
                                active_val = val

                    if active_pos is not None:
                        if active_pos != last_change_pos:
                            channel_num += 1
                            last_change_pos = active_pos

                        print(f"{frame['elapsed']:8d} {channel_num:3d} {active_pos:4d} 0x{active_val:04X} | {payload_str}")

                        if channel_num not in channel_map:
                            channel_map[channel_num] = []
                        channel_map[channel_num].append({
                            'pos': active_pos,
                            'val': active_val,
                            'payload': payload_str
                        })

    return channel_map

def analyze_channel_map(channel_map):
    """Analyze the channel map to extract HAND mode encoding."""

    print("\n\n=== CHANNEL TO BYTE MAPPING ===\n")

    for ch in sorted(channel_map.keys()):
        entries = channel_map[ch]
        positions = set(e['pos'] for e in entries)
        values = set(e['val'] for e in entries)

        print(f"Channel {ch}:")
        print(f"  Byte position(s): {', '.join(map(str, sorted(positions)))}")
        print(f"  Values observed: {', '.join(f'0x{v:02X}' for v in sorted(values))}")

        # Show progression
        print(f"  Progression:")
        for e in entries[:5]:  # First 5 occurrences
            print(f"    Pos {e['pos']}: 0x{e['val']:02X} ({e['val']:3d}, 0b{e['val']:08b})")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log'

    frames = parse_board1_frames(filename)
    print(f"Parsed {len(frames)} Board 1 frames\n")

    channel_map = identify_channel_sequence(frames)
    analyze_channel_map(channel_map)

if __name__ == '__main__':
    main()
