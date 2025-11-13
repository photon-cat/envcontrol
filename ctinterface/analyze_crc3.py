#!/usr/bin/env python3
"""
Deep dive into the varying last byte to understand what it represents.
"""

import csv

def parse_hex_bytes(hex_string):
    """Parse hex string into list of integers."""
    return [int(b, 16) for b in hex_string.split()]

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    print("="*80)
    print("Analysis of the Varying Last Byte (0xE0 vs 0x80)")
    print("="*80)

    # Analyze the bit pattern
    byte_e0 = 0xE0
    byte_80 = 0x80
    xor_diff = byte_e0 ^ byte_80

    print(f"\nBit-level analysis:")
    print(f"  0xE0 = {byte_e0:08b} = {byte_e0} decimal")
    print(f"  0x80 = {byte_80:08b} = {byte_80} decimal")
    print(f"  XOR  = {xor_diff:08b} = 0x{xor_diff:02X}")
    print(f"\n  Difference: bit 6 and bit 5 are toggled")
    print(f"  0xE0 has bits [7,6,5] set (111x xxxx)")
    print(f"  0x80 has bits [7] set     (100x xxxx)")
    print(f"  XOR = 0x60 shows bits 6,5 differ")

    # Check timing correlation
    print("\n" + "="*80)
    print("Timing Analysis")
    print("="*80)

    frames_with_timestamps = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            if record_num in [6, 7, 31]:
                timestamp = int(row['timestamp_ms'])
                elapsed = int(row['elapsed_ms'])
                all_bytes = parse_hex_bytes(row['hex_bytes'])

                # Extract activation frame
                start_pattern = [0x5C, 0xC7, 0x33, 0x35, 0x96, 0xA5, 0x65, 0x96]
                for i in range(len(all_bytes) - 19):
                    if all_bytes[i:i+8] == start_pattern:
                        frame = all_bytes[i:i+20]
                        frames_with_timestamps.append({
                            'record': record_num,
                            'timestamp': timestamp,
                            'elapsed': elapsed,
                            'last_byte': frame[19],
                            'frame': frame
                        })
                        break

    for f in frames_with_timestamps:
        print(f"\nRecord #{f['record']}:")
        print(f"  Timestamp:  {f['timestamp']} ms (absolute)")
        print(f"  Elapsed:    {f['elapsed']} ms (since capture start)")
        print(f"  Last byte:  0x{f['last_byte']:02X} = {f['last_byte']:08b}")

    # Check if last byte correlates with time
    if len(frames_with_timestamps) >= 2:
        print("\n" + "="*80)
        print("Correlation with Timing")
        print("="*80)

        for i in range(len(frames_with_timestamps) - 1):
            f1 = frames_with_timestamps[i]
            f2 = frames_with_timestamps[i + 1]

            time_diff = f2['elapsed'] - f1['elapsed']
            byte_diff = f2['last_byte'] - f1['last_byte']

            print(f"\nRecord #{f1['record']} → #{f2['record']}:")
            print(f"  Time difference:  {time_diff} ms")
            print(f"  Byte difference:  {byte_diff} (0x{f2['last_byte']:02X} - 0x{f1['last_byte']:02X})")

            # Check if byte difference correlates with time
            if time_diff > 0:
                ratio = byte_diff / time_diff if time_diff else 0
                print(f"  Ratio (byte/time): {ratio:.4f}")

    # Now analyze ALL activation-like frames in the capture to see the full range
    print("\n" + "="*80)
    print("All Activation-Style Frames in Capture")
    print("="*80)

    all_activation_frames = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            timestamp = int(row['timestamp_ms'])
            elapsed = int(row['elapsed_ms'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for frames with pattern 65 96 AA AA (activation command signature)
            for i in range(len(all_bytes) - 19):
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                    # Check if this has the activation command signature
                    if i + 19 < len(all_bytes) and all_bytes[i+6:i+10] == [0x65, 0x96, 0xAA, 0xAA]:
                        frame = all_bytes[i:i+20]
                        all_activation_frames.append({
                            'record': record_num,
                            'timestamp': timestamp,
                            'elapsed': elapsed,
                            'last_byte': frame[19],
                            'bytes_17_19': (frame[17], frame[18], frame[19])
                        })

    print(f"\nFound {len(all_activation_frames)} activation-style frames")
    print("\nLast 3 bytes of each frame:")

    unique_trailers = set()
    for f in all_activation_frames:
        trailer = f'0x{f["bytes_17_19"][0]:02X} 0x{f["bytes_17_19"][1]:02X} 0x{f["bytes_17_19"][2]:02X}'
        unique_trailers.add(trailer)
        print(f"  Record #{f['record']:3d} @ {f['elapsed']:6d}ms: {trailer} (last=0x{f['last_byte']:02X}={f['last_byte']:3d})")

    print(f"\nUnique trailer patterns: {len(unique_trailers)}")
    for trailer in sorted(unique_trailers):
        print(f"  {trailer}")

    # Check the range of last byte values
    last_bytes = [f['last_byte'] for f in all_activation_frames]
    if last_bytes:
        print(f"\nLast byte statistics:")
        print(f"  Min: 0x{min(last_bytes):02X} = {min(last_bytes)}")
        print(f"  Max: 0x{max(last_bytes):02X} = {max(last_bytes)}")
        print(f"  Unique values: {sorted(set(last_bytes))}")

    # Analyze other long frames (20 bytes) to see if they follow similar pattern
    print("\n" + "="*80)
    print("Other 20-byte Frames (Non-Activation)")
    print("="*80)

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for 20-byte frames that aren't activation commands
            for i in range(len(all_bytes) - 19):
                if len(all_bytes[i:i+20]) == 20:
                    frame = all_bytes[i:i+20]
                    # Check if it starts with header but isn't activation
                    if frame[0:3] == [0x5C, 0xC7, 0x33] and frame[6:8] != [0x65, 0x96]:
                        print(f"\nRecord #{record_num}, offset {i}:")
                        print(f"  Full frame: {' '.join(f'{b:02X}' for b in frame)}")
                        print(f"  Command: {frame[6]:02X} {frame[7]:02X}")
                        print(f"  Last 3 bytes: {frame[17]:02X} {frame[18]:02X} {frame[19]:02X}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\n1. The last byte VARIES for identical command data")
    print("   → Record #6:  0xE0 (at 1462ms elapsed)")
    print("   → Record #7:  0x80 (at 1477ms elapsed, +15ms)")
    print("   → Record #31: 0xE0 (at 6471ms elapsed, +4994ms)")
    print("\n2. The difference is 0x60 (bits 6,5 toggled)")
    print("   → 0xE0 = 11100000")
    print("   → 0x80 = 10000000")
    print("\n3. This does NOT appear to be time-based (records #6 and #31 match)")
    print("\n4. Possibilities:")
    print("   a) It's a sequence counter that wraps")
    print("   b) It's a status flag or acknowledgment field")
    print("   c) It encodes some state information")
    print("   d) It's part of a request/response mechanism")

if __name__ == '__main__':
    main()
