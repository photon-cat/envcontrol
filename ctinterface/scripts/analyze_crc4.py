#!/usr/bin/env python3
"""
Analyze all 20-byte frames with command bytes starting with 0x65
to understand the trailer byte patterns.
"""

import csv
from collections import defaultdict

def parse_hex_bytes(hex_string):
    """Parse hex string into list of integers."""
    return [int(b, 16) for b in hex_string.split()]

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    print("="*80)
    print("Analysis of 20-byte Frames with Command 0x65 XX")
    print("="*80)

    # Collect all 20-byte frames
    frames_by_command = defaultdict(list)

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            elapsed = int(row['elapsed_ms'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for 20-byte frames
            i = 0
            while i <= len(all_bytes) - 20:
                # Check if starts with header
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                    # Get the next 20 bytes
                    frame = all_bytes[i:i+20]

                    # Check if byte 6 is 0x65 (activation/special command)
                    if frame[6] == 0x65:
                        cmd_full = (frame[6], frame[7])
                        frames_by_command[cmd_full].append({
                            'record': record_num,
                            'elapsed': elapsed,
                            'frame': frame
                        })
                        i += 20
                    else:
                        i += 1
                else:
                    i += 1

    print(f"\nFound {sum(len(v) for v in frames_by_command.values())} frames with command 0x65 XX\n")

    for cmd, frames in sorted(frames_by_command.items()):
        print("="*80)
        print(f"Command: 0x{cmd[0]:02X} 0x{cmd[1]:02X} ({len(frames)} frames)")
        print("="*80)

        for f in frames:
            frame = f['frame']
            print(f"\nRecord #{f['record']:3d} @ {f['elapsed']:6d}ms:")
            print(f"  Full: {' '.join(f'{b:02X}' for b in frame)}")
            print(f"  [0-2]   Header:    {' '.join(f'{b:02X}' for b in frame[0:3])}")
            print(f"  [3]     Addr:      {frame[3]:02X}")
            print(f"  [4-5]   Field:     {' '.join(f'{b:02X}' for b in frame[4:6])}")
            print(f"  [6-7]   Command:   {' '.join(f'{b:02X}' for b in frame[6:8])}")
            print(f"  [8-16]  Data:      {' '.join(f'{b:02X}' for b in frame[8:17])}")
            print(f"  [17-19] Trailer:   {' '.join(f'{b:02X}' for b in frame[17:20])}")

        # Check if trailers are consistent
        trailers = [tuple(f['frame'][17:20]) for f in frames]
        unique_trailers = set(trailers)

        print(f"\n  Trailer analysis:")
        print(f"    Total frames:    {len(trailers)}")
        print(f"    Unique trailers: {len(unique_trailers)}")

        if len(unique_trailers) == 1:
            print(f"    ✓ CONSISTENT trailer: {' '.join(f'0x{b:02X}' for b in unique_trailers.pop())}")
        else:
            print(f"    ✗ VARIABLE trailers:")
            for trailer in sorted(unique_trailers):
                count = trailers.count(trailer)
                print(f"      {' '.join(f'0x{b:02X}' for b in trailer)} (appears {count} times)")

        # Check if only last byte varies
        if len(unique_trailers) > 1:
            first_two_bytes = [t[:2] for t in trailers]
            if len(set(first_two_bytes)) == 1:
                print(f"\n    ✓ First 2 trailer bytes CONSISTENT: {' '.join(f'0x{b:02X}' for b in first_two_bytes[0])}")
                print(f"    ✗ Only LAST byte varies:")
                last_bytes = [t[2] for t in unique_trailers]
                for lb in sorted(last_bytes):
                    print(f"      0x{lb:02X} = {lb:08b} = {lb} decimal")

                # Check XOR pattern
                if len(last_bytes) == 2:
                    xor = last_bytes[0] ^ last_bytes[1]
                    print(f"\n    XOR of two values: 0x{xor:02X} = {xor:08b}")

    # Now check normal polling commands for comparison
    print("\n" + "="*80)
    print("Normal Polling Commands (11 bytes) for Comparison")
    print("="*80)

    polling_by_board = defaultdict(list)

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for 11-byte polling frames
            i = 0
            while i <= len(all_bytes) - 11:
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                    # Check if this is an 11-byte frame (not part of longer frame)
                    # and has normal polling pattern (command bytes 0x35 XX)
                    if i + 11 <= len(all_bytes):
                        frame = all_bytes[i:i+11]
                        if frame[6] == 0x35:  # Normal polling command
                            board = frame[3]
                            polling_by_board[board].append({
                                'record': record_num,
                                'frame': frame,
                                'last_byte': frame[10]
                            })
                            i += 11
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1

    for board, frames in sorted(polling_by_board.items()):
        print(f"\nBoard 0x{board:02X}: {len(frames)} frames")
        last_bytes = [f['last_byte'] for f in frames]
        unique_last = set(last_bytes)

        if len(unique_last) == 1:
            print(f"  ✓ FIXED last byte: 0x{last_bytes[0]:02X}")
        else:
            print(f"  ✗ VARIABLE last bytes: {sorted(f'0x{b:02X}' for b in unique_last)}")

        # Show first 3 examples
        for i, f in enumerate(frames[:3]):
            print(f"    Example: {' '.join(f'{b:02X}' for b in f['frame'])}")

    print("\n" + "="*80)
    print("FINDINGS")
    print("="*80)
    print("\n1. Normal polling (command 0x35 XX) has FIXED last byte per board")
    print("   → This byte is a board identifier, NOT a checksum")
    print("\n2. Activation commands (0x65 0x96) have VARIABLE last byte")
    print("   → Only the last of 3 trailer bytes varies")
    print("   → The first 2 trailer bytes (0xA9 0x9A) are consistent")
    print("\n3. Other 0x65 XX commands (0x65 0x95, 0x65 0x99) should show similar pattern")
    print("\n4. The varying byte is likely:")
    print("   a) A sequence/transaction counter")
    print("   b) A status/acknowledgment flag")
    print("   c) Part of a request-response protocol")
    print("\n5. Protocol uses 8E1 (Even parity) for hardware error detection")
    print("   → No application-level CRC/checksum appears to be present")

if __name__ == '__main__':
    main()
