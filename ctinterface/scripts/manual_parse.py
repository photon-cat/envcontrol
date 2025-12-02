#!/usr/bin/env python3
"""
Manual parsing - let's look at the actual byte sequences to understand structure.
"""

import csv
from collections import defaultdict

def parse_hex(s):
    return s.strip().split()

# Read first 50 records and manually identify the pattern
filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

print("=" * 80)
print("MANUAL FRAME STRUCTURE ANALYSIS")
print("=" * 80)
print()

with open(filename, 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 50:
            break

        rec_num = int(row['record_num'])
        elapsed = int(row['elapsed_ms'])
        data = parse_hex(row['hex_bytes'])

        print(f"\nRec {rec_num} ({elapsed}ms): {len(data)} bytes")

        # Find all 5C C7 33 positions
        sync_positions = []
        for j in range(len(data) - 2):
            if data[j:j+3] == ['5C', 'C7', '33']:
                sync_positions.append(j)

        print(f"  Sync headers at positions: {sync_positions}")

        # Analyze structure between sync headers
        for k, pos in enumerate(sync_positions):
            # After sync (3 bytes), show next 24 bytes
            segment_end = min(pos + 27, len(data))
            segment = data[pos:segment_end]

            # Try to identify: sync (3) + addr/status (variable) + payload (16) + checksum (variable)
            print(f"  Segment {k+1} @ pos {pos}:")
            print(f"    {' '.join(segment[:3])} | {' '.join(segment[3:])}")

            # If there's another sync header, show distance
            if k + 1 < len(sync_positions):
                distance = sync_positions[k+1] - pos
                print(f"    Distance to next sync: {distance} bytes")

                # Extract what's between this sync and the next
                between = data[pos:sync_positions[k+1]]
                print(f"    Full frame ({len(between)} bytes): {' '.join(between)}")

print("\n" + "=" * 80)
print("PATTERN IDENTIFICATION")
print("=" * 80)
print()

print("Looking at the data, here's the pattern I see:")
print()
print("Record 2: 5C C7 33 56 56 A5 35 9A 35 35 A6 00 | 5C C7 33 35 5A 35 65 35 35 35 35 35 35 35 35 A9 95 AA 56")
print("          [Sync]  [8 bytes status]        [??]   [Sync]  [16 bytes - payload?]                [3 checksum?]")
print()
print("Let me check if pattern is: 5C C7 33 [8 status] [1 byte] then next frame")
print()

# Now let's extract assuming the payload is in a different location
# Looking at record 13 which has multiple complete frames:
print("=" * 80)
print("ANALYZING RECORD 13 (has complete multi-board frame)")
print("=" * 80)
print()

with open(filename, 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if int(row['record_num']) == 13:
            data = parse_hex(row['hex_bytes'])
            print(f"Record 13: {len(data)} bytes")
            print(f"Raw: {' '.join(data)}")
            print()

            # Find syncs
            syncs = []
            for j in range(len(data) - 2):
                if data[j:j+3] == ['5C', 'C7', '33']:
                    syncs.append(j)

            print(f"Found {len(syncs)} sync headers at: {syncs}")
            print()

            # Extract each frame
            for k in range(len(syncs)):
                start = syncs[k]
                end = syncs[k+1] if k+1 < len(syncs) else len(data)
                frame = data[start:end]

                print(f"Frame {k+1} (positions {start}-{end-1}, {len(frame)} bytes):")
                print(f"  Sync: {' '.join(frame[0:3])}")
                if len(frame) > 3:
                    print(f"  Rest: {' '.join(frame[3:])}")
                print()

print("=" * 80)
print("HYPOTHESIS: Second sync header payload extraction")
print("=" * 80)
print()

# Let's try extracting the 16-byte blocks that appear AFTER "35 5A 35 65"
# Looking at the pattern, many frames contain: ... 5C C7 33 35 5A 35 65 35 35 ...
# Those last bytes (35 35 ...) might be the actual channel payloads

with open(filename, 'r') as f:
    reader = csv.DictReader(f)

    pattern_35_5A_35_65 = ['35', '5A', '35', '65']

    found_payloads = []

    for row in reader:
        rec_num = int(row['record_num'])
        elapsed = int(row['elapsed_ms'])
        data = parse_hex(row['hex_bytes'])

        # Find pattern "35 5A 35 65"
        for j in range(len(data) - 3):
            if data[j:j+4] == pattern_35_5A_35_65:
                # After this pattern, extract next 12 bytes (16 total)
                payload_start = j
                payload_end = payload_start + 16

                if payload_end <= len(data):
                    payload = data[payload_start:payload_end]
                    found_payloads.append({
                        'record': rec_num,
                        'elapsed': elapsed,
                        'pos': j,
                        'payload': payload
                    })

print(f"Found {len(found_payloads)} instances of pattern '35 5A 35 65' with 16-byte blocks")
print("\nFirst 20:")
for i, p in enumerate(found_payloads[:20]):
    print(f"  Rec {p['record']:3d} @ pos {p['pos']:3d}: {' '.join(p['payload'])}")
