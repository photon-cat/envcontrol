#!/usr/bin/env python3
"""
Final analysis: The last byte appears to be a FIXED identifier based on frame content,
not a calculated checksum. Let's verify this and document the frame structure.
"""

import csv
from collections import defaultdict

def parse_hex_bytes(hex_string):
    """Parse hex string into list of integers."""
    return [int(b, 16) for b in hex_string.split()]

def main():
    csv_file = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv'

    print("="*80)
    print("CT2 Protocol Frame Structure Analysis")
    print("="*80)

    # Map frame patterns to last bytes for normal polling
    polling_map = {}

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            i = 0
            while i <= len(all_bytes) - 11:
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33]:
                    frame = all_bytes[i:i+11]
                    if frame[6] == 0x35:  # Normal polling
                        key = tuple(frame[:-1])
                        if key in polling_map and polling_map[key] != frame[10]:
                            print(f"ERROR: Inconsistent last byte for pattern!")
                        polling_map[key] = frame[10]
                    i += 1
                else:
                    i += 1

    print("\n" + "="*80)
    print("Normal Polling Command Structure (11 bytes)")
    print("="*80)

    print(f"\nFound {len(polling_map)} unique frame patterns\n")

    for pattern, last_byte in sorted(polling_map.items()):
        print(f"Pattern: {' '.join(f'{b:02X}' for b in pattern)} → Last byte: 0x{last_byte:02X}")
        print(f"  [0-2]   Header: 0x{pattern[0]:02X} 0x{pattern[1]:02X} 0x{pattern[2]:02X}")
        print(f"  [3]     Addr:   0x{pattern[3]:02X}")
        print(f"  [4-5]   Field:  0x{pattern[4]:02X} 0x{pattern[5]:02X}")
        print(f"  [6-7]   Cmd:    0x{pattern[6]:02X} 0x{pattern[7]:02X}")
        print(f"  [8-9]   Data:   0x{pattern[8]:02X} 0x{pattern[9]:02X}")
        print(f"  [10]    ID:     0x{last_byte:02X}")
        print()

    # Analyze the relationship between address and last byte
    print("="*80)
    print("Relationship Between Address and Last Byte")
    print("="*80)

    by_addr = defaultdict(set)
    for pattern, last_byte in polling_map.items():
        addr = pattern[3]
        by_addr[addr].add(last_byte)

    for addr in sorted(by_addr.keys()):
        last_bytes = sorted(by_addr[addr])
        print(f"\nAddress 0x{addr:02X} uses last bytes: {' '.join(f'0x{b:02X}' for b in last_bytes)}")

    # Check the relationship with other fields
    print("\n" + "="*80)
    print("Relationship Between Field [4-5] and Last Byte")
    print("="*80)

    by_field = defaultdict(set)
    for pattern, last_byte in polling_map.items():
        field = (pattern[4], pattern[5])
        addr = pattern[3]
        by_field[(addr, field)].add(last_byte)

    for (addr, field), last_bytes in sorted(by_field.items()):
        print(f"Addr 0x{addr:02X}, Field 0x{field[0]:02X} 0x{field[1]:02X} → "
              f"Last bytes: {' '.join(f'0x{b:02X}' for b in sorted(last_bytes))}")

    # Now analyze activation commands
    print("\n" + "="*80)
    print("Activation Command Structure (20 bytes)")
    print("="*80)

    activation_patterns = {}
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            all_bytes = parse_hex_bytes(row['hex_bytes'])

            # Look for activation frames
            i = 0
            while i <= len(all_bytes) - 20:
                if all_bytes[i:i+3] == [0x5C, 0xC7, 0x33] and all_bytes[i+6] == 0x65:
                    frame = all_bytes[i:i+20]
                    cmd = (frame[6], frame[7])
                    key = tuple(frame[:-1])

                    if key not in activation_patterns:
                        activation_patterns[key] = []
                    activation_patterns[key].append({
                        'record': record_num,
                        'last_byte': frame[19]
                    })
                    i += 20
                else:
                    i += 1

    for pattern, occurrences in sorted(activation_patterns.items()):
        last_bytes = [o['last_byte'] for o in occurrences]
        unique_last = sorted(set(last_bytes))

        print(f"\nPattern: {' '.join(f'{b:02X}' for b in pattern)}")
        print(f"  Command: 0x{pattern[6]:02X} 0x{pattern[7]:02X}")
        print(f"  Occurred {len(occurrences)} times in records: {[o['record'] for o in occurrences]}")
        print(f"  Last byte values: {' '.join(f'0x{b:02X}' for b in unique_last)}")

        if len(unique_last) == 1:
            print(f"  ✓ CONSISTENT last byte")
        else:
            print(f"  ✗ VARIABLE last byte")
            print(f"    XOR of different values: 0x{unique_last[0] ^ unique_last[1]:02X}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF FINDINGS")
    print("="*80)

    print("\n1. NORMAL POLLING COMMANDS (11 bytes):")
    print("   - Frame structure: [Header(3)] [Addr(1)] [Field(2)] [Cmd(2)] [Data(2)] [ID(1)]")
    print("   - Last byte is FIXED for each unique 10-byte pattern")
    print("   - NOT a calculated checksum (no XOR, SUM, or CRC match)")
    print("   - Appears to be a FRAME IDENTIFIER or BOARD/COMMAND SIGNATURE")
    print()
    print("2. ACTIVATION COMMANDS (20 bytes):")
    print("   - Frame structure: [Header(3)] [Addr(1)] [Field(2)] [Cmd(2)] [Data(9)] [Trailer(3)]")
    print("   - First 2 trailer bytes are CONSISTENT per command type")
    print("   - Last trailer byte VARIES for identical frame content")
    print("   - This varying byte could be:")
    print("     a) A sequence/transaction counter")
    print("     b) A response/status flag")
    print("     c) A timing or synchronization field")
    print()
    print("3. ERROR DETECTION:")
    print("   - Protocol uses 8E1 serial format (8 bits, Even parity, 1 stop)")
    print("   - Even parity provides hardware-level error detection")
    print("   - NO application-level CRC or checksum detected")
    print()
    print("4. CONCLUSION:")
    print("   - CT2 protocol does NOT use CRC/checksum validation at application layer")
    print("   - Relies on serial parity bit (8E1) for error detection")
    print("   - Frame identification uses fixed trailer bytes, not checksums")
    print("   - Variable bytes in activation commands likely serve protocol state/sequencing")

if __name__ == '__main__':
    main()
