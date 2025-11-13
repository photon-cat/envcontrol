#!/usr/bin/env python3
"""
Detailed analysis of CT2 protocol frames focusing on the specific records mentioned.
"""

import csv

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

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    # Target records with activation commands
    target_records = [6, 7, 31]

    print("="*80)
    print("CT2 Protocol - Detailed Analysis of Activation Commands")
    print("="*80)

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])

            if record_num in target_records:
                hex_bytes = row['hex_bytes']
                timestamp = row['timestamp_ms']

                print(f"\n{'='*80}")
                print(f"Record #{record_num} (timestamp: {timestamp}ms)")
                print(f"{'='*80}")
                print(f"Full data: {hex_bytes}")
                print(f"Length: {len(hex_bytes.split())} bytes")

                # Parse the frame - note that record #7 contains multiple frames
                all_bytes = parse_hex_bytes(hex_bytes)
                print(f"\nTotal bytes in record: {len(all_bytes)}")

                # Look for activation command pattern: starts with 5C C7 33 35 96 A5 65 96
                start_pattern = [0x5C, 0xC7, 0x33, 0x35, 0x96, 0xA5, 0x65, 0x96]

                # Find all occurrences of the pattern
                i = 0
                frame_num = 0
                while i < len(all_bytes) - len(start_pattern):
                    if all_bytes[i:i+len(start_pattern)] == start_pattern:
                        frame_num += 1
                        # Extract 20-byte frame
                        if i + 20 <= len(all_bytes):
                            frame = all_bytes[i:i+20]
                            print(f"\n  Frame {frame_num} (starting at byte offset {i}):")
                            print(f"    Bytes: {' '.join(f'{b:02X}' for b in frame)}")

                            # Detailed breakdown
                            print(f"\n    Byte-by-byte structure:")
                            print(f"      [0-2]   Header:     {' '.join(f'{b:02X}' for b in frame[0:3])}")
                            print(f"      [3]     Addr/ID:    {frame[3]:02X}")
                            print(f"      [4-5]   Unknown:    {' '.join(f'{b:02X}' for b in frame[4:6])}")
                            print(f"      [6-7]   Command:    {' '.join(f'{b:02X}' for b in frame[6:8])}")
                            print(f"      [8-16]  Data:       {' '.join(f'{b:02X}' for b in frame[8:17])}")
                            print(f"      [17]    Trailer-1:  {frame[17]:02X}")
                            print(f"      [18]    Trailer-2:  {frame[18]:02X}")
                            print(f"      [19]    Trailer-3:  {frame[19]:02X}")

                            # Test checksums on different portions
                            print(f"\n    Checksum analysis:")

                            # Test 1: Last byte as checksum of bytes 0-18
                            data1 = frame[0:19]
                            print(f"\n      Test 1: Last byte (0x{frame[19]:02X}) as checksum of bytes 0-18:")
                            print(f"        XOR(0-18):      0x{calculate_xor_checksum(data1):02X}")
                            print(f"        SUM(0-18):      0x{calculate_sum_checksum(data1):02X}")
                            print(f"        CRC8(0-18):     0x{calculate_crc8(data1, 0x07):02X}")

                            # Test 2: Last 2 bytes as 16-bit checksum
                            data2 = frame[0:18]
                            last_word = (frame[18] << 8) | frame[19]
                            print(f"\n      Test 2: Last 2 bytes (0x{frame[18]:02X}{frame[19]:02X} = 0x{last_word:04X}) as checksum of bytes 0-17:")
                            print(f"        XOR(0-17):      0x{calculate_xor_checksum(data2):02X}")
                            print(f"        SUM(0-17):      0x{calculate_sum_checksum(data2):02X}")

                            # Test 3: Last 3 bytes as trailer/metadata
                            data3 = frame[0:17]
                            print(f"\n      Test 3: Last 3 bytes as trailer/metadata, checksum on bytes 0-16:")
                            print(f"        XOR(0-16):      0x{calculate_xor_checksum(data3):02X}")
                            print(f"        SUM(0-16):      0x{calculate_sum_checksum(data3):02X}")
                            print(f"        CRC8(0-16):     0x{calculate_crc8(data3, 0x07):02X}")

                            i += 20
                        else:
                            print(f"\n  Incomplete frame starting at offset {i}")
                            break
                    else:
                        i += 1

                # Also look for the normal polling pattern in this record
                # Pattern: 5C C7 33 [addr] [data...] (11 bytes total)
                i = 0
                while i < len(all_bytes) - 11:
                    if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                        # Check if this looks like an 11-byte frame
                        if i + 11 <= len(all_bytes):
                            frame = all_bytes[i:i+11]
                            # Verify it's not the start of a 20-byte activation frame
                            if not (len(all_bytes) >= i + 20 and all_bytes[i:i+8] == start_pattern):
                                print(f"\n  Normal polling frame at offset {i}:")
                                print(f"    Bytes: {' '.join(f'{b:02X}' for b in frame)}")
                                print(f"    Last byte: 0x{frame[10]:02X}")
                    i += 1

    # Now compare the three activation commands
    print("\n" + "="*80)
    print("COMPARISON OF ACTIVATION COMMANDS")
    print("="*80)

    activation_frames = {}
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            if record_num in target_records:
                all_bytes = parse_hex_bytes(row['hex_bytes'])
                start_pattern = [0x5C, 0xC7, 0x33, 0x35, 0x96, 0xA5, 0x65, 0x96]

                for i in range(len(all_bytes) - 19):
                    if all_bytes[i:i+8] == start_pattern:
                        frame = all_bytes[i:i+20]
                        activation_frames[record_num] = frame
                        break

    if len(activation_frames) >= 2:
        records = sorted(activation_frames.keys())
        print(f"\nFound activation frames in records: {records}")

        for i in range(len(records)):
            rec_i = records[i]
            frame_i = activation_frames[rec_i]

            for j in range(i+1, len(records)):
                rec_j = records[j]
                frame_j = activation_frames[rec_j]

                print(f"\nComparing Record #{rec_i} vs Record #{rec_j}:")

                # Compare byte by byte
                differences = []
                for k in range(min(len(frame_i), len(frame_j))):
                    if frame_i[k] != frame_j[k]:
                        differences.append(k)

                if differences:
                    print(f"  Differences at byte positions: {differences}")
                    for pos in differences:
                        print(f"    Byte[{pos}]: 0x{frame_i[pos]:02X} vs 0x{frame_j[pos]:02X} (diff: {abs(frame_i[pos]-frame_j[pos])})")
                else:
                    print(f"  Frames are IDENTICAL")

    print("\n" + "="*80)
    print("CONCLUSIONS")
    print("="*80)
    print("\n1. If the last byte varies for otherwise identical frames,")
    print("   it is NOT a checksum of the data.")
    print("\n2. It could be:")
    print("   - A sequence counter")
    print("   - A timestamp or timing field")
    print("   - A status/state indicator")
    print("   - Part of a multi-frame sequence")
    print("\n3. The protocol uses 8E1 (8 data bits, Even parity, 1 stop bit)")
    print("   which provides hardware-level error detection via parity bit.")

if __name__ == '__main__':
    main()
