#!/usr/bin/env python3
"""
Analyze CT2 protocol frames for CRC/checksum validation.
Focus on activation commands and normal polling to identify patterns.
"""

import csv
import sys
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

def calculate_sum_checksum(data):
    """Calculate simple sum checksum (8-bit)."""
    return sum(data) & 0xFF

def calculate_crc8(data, poly=0x07, init=0x00):
    """Calculate CRC-8 with given polynomial."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc = crc << 1
            crc &= 0xFF
    return crc

def calculate_crc16(data, poly=0x8005, init=0xFFFF):
    """Calculate CRC-16 with given polynomial."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc

def analyze_frame(frame_bytes):
    """Analyze a single frame and calculate various checksums."""
    if len(frame_bytes) < 2:
        return None

    # Try different checksum positions (last 1 or 2 bytes)
    results = {}

    # Assume last byte is checksum
    data = frame_bytes[:-1]
    checksum = frame_bytes[-1]

    results['xor'] = calculate_xor_checksum(data)
    results['sum'] = calculate_sum_checksum(data)
    results['crc8_0x07'] = calculate_crc8(data, poly=0x07)
    results['crc8_0x31'] = calculate_crc8(data, poly=0x31)
    results['crc8_0x07_ff'] = calculate_crc8(data, poly=0x07, init=0xFF)
    results['actual_last'] = checksum

    # Try last 2 bytes as CRC-16
    if len(frame_bytes) >= 3:
        data16 = frame_bytes[:-2]
        checksum16 = (frame_bytes[-2] << 8) | frame_bytes[-1]
        results['crc16_8005'] = calculate_crc16(data16, poly=0x8005)
        results['crc16_1021'] = calculate_crc16(data16, poly=0x1021)
        results['actual_last2'] = checksum16

    return results

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    print("="*80)
    print("CT2 Protocol CRC/Checksum Analysis")
    print("="*80)

    # Store frames by pattern
    activation_frames = []
    normal_polling = defaultdict(list)

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            hex_bytes = row['hex_bytes']
            frame_bytes = parse_hex_bytes(hex_bytes)

            # Look for activation commands (20 bytes, contains AA pattern)
            if len(frame_bytes) == 20 and frame_bytes.count(0xAA) >= 8:
                activation_frames.append({
                    'record': record_num,
                    'bytes': frame_bytes,
                    'hex': hex_bytes
                })

            # Look for normal polling (11 bytes starting with 5C C7 33)
            elif len(frame_bytes) == 11 and frame_bytes[:3] == [0x5C, 0xC7, 0x33]:
                # Identify board by byte 3
                board_id = frame_bytes[3]
                normal_polling[board_id].append({
                    'record': record_num,
                    'bytes': frame_bytes,
                    'hex': hex_bytes
                })

    print("\n" + "="*80)
    print("ACTIVATION COMMANDS ANALYSIS")
    print("="*80)

    for frame in activation_frames:
        print(f"\nRecord #{frame['record']}:")
        print(f"  Bytes: {frame['hex']}")
        print(f"  Length: {len(frame['bytes'])} bytes")

        # Show structure
        fb = frame['bytes']
        print(f"\n  Structure breakdown:")
        print(f"    Header:    {' '.join(f'{b:02X}' for b in fb[0:6])}")
        print(f"    Command:   {' '.join(f'{b:02X}' for b in fb[6:8])}")
        print(f"    Data:      {' '.join(f'{b:02X}' for b in fb[8:17])}")
        print(f"    Trailer:   {' '.join(f'{b:02X}' for b in fb[17:20])}")
        print(f"    Last byte: 0x{fb[-1]:02X}")

        # Calculate checksums
        checksums = analyze_frame(fb)
        print(f"\n  Checksum analysis (assuming last byte is checksum):")
        print(f"    Actual last byte: 0x{checksums['actual_last']:02X}")
        print(f"    XOR checksum:     0x{checksums['xor']:02X} {'✓ MATCH' if checksums['xor'] == checksums['actual_last'] else ''}")
        print(f"    SUM checksum:     0x{checksums['sum']:02X} {'✓ MATCH' if checksums['sum'] == checksums['actual_last'] else ''}")
        print(f"    CRC-8 (0x07):     0x{checksums['crc8_0x07']:02X} {'✓ MATCH' if checksums['crc8_0x07'] == checksums['actual_last'] else ''}")
        print(f"    CRC-8 (0x31):     0x{checksums['crc8_0x31']:02X} {'✓ MATCH' if checksums['crc8_0x31'] == checksums['actual_last'] else ''}")
        print(f"    CRC-8 (0x07,FF):  0x{checksums['crc8_0x07_ff']:02X} {'✓ MATCH' if checksums['crc8_0x07_ff'] == checksums['actual_last'] else ''}")

        if 'crc16_8005' in checksums:
            print(f"\n  CRC-16 analysis (assuming last 2 bytes):")
            print(f"    Actual last 2:    0x{checksums['actual_last2']:04X}")
            print(f"    CRC-16 (0x8005):  0x{checksums['crc16_8005']:04X} {'✓ MATCH' if checksums['crc16_8005'] == checksums['actual_last2'] else ''}")
            print(f"    CRC-16 (0x1021):  0x{checksums['crc16_1021']:04X} {'✓ MATCH' if checksums['crc16_1021'] == checksums['actual_last2'] else ''}")

    # Compare activation frames
    print("\n" + "="*80)
    print("ACTIVATION FRAMES COMPARISON")
    print("="*80)

    if len(activation_frames) >= 2:
        print("\nComparing identical commands with different last bytes:")
        for i in range(len(activation_frames)):
            for j in range(i+1, len(activation_frames)):
                f1 = activation_frames[i]['bytes']
                f2 = activation_frames[j]['bytes']

                # Check if frames are identical except last byte
                if f1[:-1] == f2[:-1] and f1[-1] != f2[-1]:
                    print(f"\nRecord #{activation_frames[i]['record']} vs #{activation_frames[j]['record']}:")
                    print(f"  First 19 bytes: IDENTICAL")
                    print(f"  Last byte: 0x{f1[-1]:02X} vs 0x{f2[-1]:02X}")
                    print(f"  Difference: {abs(f1[-1] - f2[-1])} (0x{abs(f1[-1] - f2[-1]):02X})")

                    # Check what differs
                    diff_bits = f1[-1] ^ f2[-1]
                    print(f"  XOR of last bytes: 0x{diff_bits:02X} (binary: {diff_bits:08b})")

    print("\n" + "="*80)
    print("NORMAL POLLING COMMANDS ANALYSIS")
    print("="*80)

    for board_id, frames in sorted(normal_polling.items()):
        print(f"\nBoard ID 0x{board_id:02X} - {len(frames)} frames:")

        # Take first 3 examples
        for frame in frames[:3]:
            fb = frame['bytes']
            print(f"\n  Record #{frame['record']}:")
            print(f"    Bytes: {frame['hex']}")

            checksums = analyze_frame(fb)
            print(f"    Last byte: 0x{checksums['actual_last']:02X}")
            print(f"    XOR: 0x{checksums['xor']:02X} {'✓' if checksums['xor'] == checksums['actual_last'] else '✗'}")
            print(f"    SUM: 0x{checksums['sum']:02X} {'✓' if checksums['sum'] == checksums['actual_last'] else '✗'}")

        # Check consistency
        last_bytes = [f['bytes'][-1] for f in frames]
        if len(set(last_bytes)) == 1:
            print(f"\n  ✓ All frames have CONSISTENT last byte: 0x{last_bytes[0]:02X}")
            print(f"    → This suggests it's a FIXED identifier, NOT a checksum")
        else:
            print(f"\n  ✗ Last byte VARIES: {set(f'0x{b:02X}' for b in last_bytes)}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("\n1. Activation commands show VARYING last byte for identical data")
    print("   → This rules out traditional CRC/checksum on the data portion")
    print("   → The varying byte may be a sequence number or timing field")

    print("\n2. Normal polling commands have FIXED last byte per board")
    print("   → Board 1: constant trailer")
    print("   → Board 2: constant trailer")
    print("   → Board 3: constant trailer")
    print("   → This suggests board identifier rather than checksum")

    print("\n3. The 8E1 serial format includes:")
    print("   → Even parity bit (hardware level)")
    print("   → This provides basic error detection at the byte level")
    print("   → May explain lack of application-level CRC")

if __name__ == '__main__':
    main()
