#!/usr/bin/env python3
"""
Final deep analysis: correlate the varying last byte with other frame fields
to determine what it represents.
"""

import csv
from collections import defaultdict

def parse_hex_bytes(hex_string):
    """Parse hex string into list of integers."""
    return [int(b, 16) for b in hex_string.split()]

def calculate_xor_checksum(data):
    """Calculate simple XOR checksum."""
    result = 0
    for byte in data:
        result ^= byte
    return result

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    print("="*80)
    print("Correlation Analysis: What Determines the Last Byte?")
    print("="*80)

    # Analyze normal polling commands in detail
    print("\n" + "="*80)
    print("Normal Polling Commands - Detailed Analysis")
    print("="*80)

    polling_frames = []

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for standalone 11-byte frames
            i = 0
            while i <= len(all_bytes) - 11:
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                    frame = all_bytes[i:i+11]
                    if frame[6] == 0x35:  # Normal polling
                        polling_frames.append({
                            'record': record_num,
                            'frame': frame,
                            'last_byte': frame[10]
                        })
                    i += 1
                else:
                    i += 1

    # Group by everything except last byte
    frame_groups = defaultdict(list)
    for pf in polling_frames:
        key = tuple(pf['frame'][:-1])  # Everything except last byte
        frame_groups[key].append(pf)

    print(f"\nTotal polling frames analyzed: {len(polling_frames)}")
    print(f"Unique frame patterns (excluding last byte): {len(frame_groups)}")

    print("\nFrames grouped by content (first 10 bytes):")
    for i, (key, frames) in enumerate(sorted(frame_groups.items())[:10]):
        last_bytes = [f['last_byte'] for f in frames]
        unique_last = set(last_bytes)

        print(f"\n  Pattern {i+1}: {' '.join(f'{b:02X}' for b in key)}")
        print(f"    Appears in {len(frames)} records: {[f['record'] for f in frames[:5]]}" +
              ("..." if len(frames) > 5 else ""))
        print(f"    Last byte values: {sorted(f'0x{b:02X}' for b in unique_last)}")

        if len(unique_last) == 1:
            print(f"    ✓ CONSISTENT")
            # Test if it's a checksum
            xor = calculate_xor_checksum(key)
            print(f"    XOR(0-9): 0x{xor:02X} {'✓ MATCH' if xor == last_bytes[0] else '✗ no match'}")
        else:
            print(f"    ✗ VARIES")

    # Now look at what varies between frames with same pattern
    print("\n" + "="*80)
    print("Testing Checksum Hypothesis on Varying Frames")
    print("="*80)

    # Find frames where only byte 4 or 5 differs
    test_frames = []
    for pf in polling_frames[:20]:
        test_frames.append(pf['frame'])

    for i in range(len(test_frames)):
        for j in range(i+1, len(test_frames)):
            f1 = test_frames[i]
            f2 = test_frames[j]

            # Find differences (excluding last byte)
            diffs = []
            for k in range(10):
                if f1[k] != f2[k]:
                    diffs.append(k)

            # If only 1-2 bytes differ, analyze
            if 1 <= len(diffs) <= 2:
                print(f"\nComparing frames:")
                print(f"  Frame 1: {' '.join(f'{b:02X}' for b in f1)}")
                print(f"  Frame 2: {' '.join(f'{b:02X}' for b in f2)}")
                print(f"  Differences at positions: {diffs}")
                for d in diffs:
                    print(f"    Byte[{d}]: 0x{f1[d]:02X} vs 0x{f2[d]:02X}")
                print(f"  Last byte: 0x{f1[10]:02X} vs 0x{f2[10]:02X}")

                # Test if last byte is XOR checksum
                xor1 = calculate_xor_checksum(f1[:-1])
                xor2 = calculate_xor_checksum(f2[:-1])
                print(f"  XOR checksums: 0x{xor1:02X} vs 0x{xor2:02X}")
                print(f"  Match: {xor1 == f1[10]} and {xor2 == f2[10]}")

                # Calculate what last byte change corresponds to data changes
                last_xor = f1[10] ^ f2[10]
                data_xor = 0
                for d in diffs:
                    data_xor ^= (f1[d] ^ f2[d])
                print(f"  XOR of last bytes: 0x{last_xor:02X}")
                print(f"  XOR of changed data: 0x{data_xor:02X}")
                print(f"  {'✓ MATCH' if last_xor == data_xor else '✗ no correlation'}")

                break  # Only show first example
        else:
            continue
        break

    # Final test: check all frames for XOR checksum
    print("\n" + "="*80)
    print("XOR Checksum Test on ALL Polling Frames")
    print("="*80)

    matches = 0
    total = 0
    for pf in polling_frames:
        frame = pf['frame']
        xor = calculate_xor_checksum(frame[:-1])
        if xor == frame[10]:
            matches += 1
        total += 1

    print(f"\nFrames where last byte = XOR(first 10 bytes): {matches}/{total}")
    if matches == total:
        print("✓ ALL frames match! Last byte IS an XOR checksum!")
    elif matches > 0:
        print(f"Partial match ({100*matches/total:.1f}%). May be XOR-based with modifications.")
    else:
        print("✗ No matches. Not a simple XOR checksum.")

    # Show examples of matches and mismatches
    print("\nExamples:")
    for pf in polling_frames[:5]:
        frame = pf['frame']
        xor = calculate_xor_checksum(frame[:-1])
        match = "✓" if xor == frame[10] else "✗"
        print(f"  Record #{pf['record']:3d}: {' '.join(f'{b:02X}' for b in frame)} "
              f"XOR=0x{xor:02X} {match}")

    # Test on activation commands
    print("\n" + "="*80)
    print("XOR Checksum Test on Activation Commands")
    print("="*80)

    activation_frames = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            start_pattern = [0x5C, 0xC7, 0x33, 0x35, 0x96, 0xA5, 0x65, 0x96]
            for i in range(len(all_bytes) - 19):
                if all_bytes[i:i+8] == start_pattern:
                    frame = all_bytes[i:i+20]
                    activation_frames.append({
                        'record': record_num,
                        'frame': frame
                    })
                    break

    for af in activation_frames:
        frame = af['frame']
        print(f"\nRecord #{af['record']}:")
        print(f"  Frame: {' '.join(f'{b:02X}' for b in frame)}")

        # Test different checksum positions
        tests = [
            ("Last byte on [0-18]", frame[:-1], frame[19]),
            ("Last byte on [0-16]", frame[:-3], frame[19]),
            ("Byte 18 on [0-17]", frame[:-2], frame[18]),
            ("Byte 17 on [0-16]", frame[:-3], frame[17]),
        ]

        for desc, data, actual in tests:
            xor = calculate_xor_checksum(data)
            match = "✓" if xor == actual else "✗"
            print(f"    {desc:20s}: XOR=0x{xor:02X} actual=0x{actual:02X} {match}")

if __name__ == '__main__':
    main()
