#!/usr/bin/env python3
"""
Analyze CT2 protocol capture file to identify frame structure and state transitions.
Extracts payload blocks and maps channel states.
"""

import csv
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Set

# Sync header pattern
SYNC_HEADER = ['5C', 'C7', '33']

def parse_hex_line(hex_bytes: str) -> List[str]:
    """Parse hex bytes string into list of hex values."""
    return hex_bytes.strip().split()

def find_sync_headers(data: List[str]) -> List[int]:
    """Find all positions of sync headers in data."""
    positions = []
    for i in range(len(data) - 2):
        if data[i:i+3] == SYNC_HEADER:
            positions.append(i)
    return positions

def extract_frames(data: List[str]) -> List[Dict]:
    """Extract all frames from the data stream."""
    frames = []
    sync_positions = find_sync_headers(data)

    for pos in sync_positions:
        # After sync header (3 bytes), we have status bytes, then payload
        # Based on the data, it looks like:
        # 5C C7 33 [status bytes] [payload 16 bytes or status indicators]
        if pos + 3 < len(data):
            # Extract the next 8 bytes after sync as status
            status_end = min(pos + 11, len(data))
            status = data[pos+3:status_end]

            # Check if there are payload bytes after status
            payload_start = status_end
            payload_end = min(payload_start + 16, len(data))

            # Only consider as payload if we have enough bytes and they look like payload
            # Payload bytes are typically in ranges like 35, 59, 5A, 65, 95, 99, AA, etc.
            payload = []
            if payload_end - payload_start >= 10:
                potential_payload = data[payload_start:payload_end]
                # Check if next sequence starts with sync header (to avoid reading into next frame)
                next_sync = None
                for i in range(len(potential_payload) - 2):
                    if potential_payload[i:i+3] == SYNC_HEADER:
                        next_sync = i
                        break
                if next_sync:
                    payload = potential_payload[:next_sync]
                else:
                    payload = potential_payload

            if payload:
                frames.append({
                    'sync_pos': pos,
                    'status': status,
                    'payload': payload
                })

    return frames

def identify_board_frames(all_data: List[str], record_num: int, timestamp: int) -> Dict:
    """Identify which frames belong to which board in a single record."""
    frames = extract_frames(all_data)

    result = {
        'record_num': record_num,
        'timestamp': timestamp,
        'board1': None,
        'board2': None,
        'board3': None,
        'frames': frames
    }

    # Typically we see 3 frames per record for boards 1, 2, 3
    # The pattern seems to be alternating status bytes in position 3-4
    # Board identification might be in the status bytes
    for i, frame in enumerate(frames):
        if len(frame['payload']) >= 12:
            result[f'board{i+1}'] = frame['payload'][:16]

    return result

def analyze_capture_file(filename: str):
    """Main analysis function."""

    print("=" * 80)
    print("CT2 Protocol Capture Analysis")
    print("=" * 80)
    print()

    # Storage for all records
    all_records = []

    # Read CSV file
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            timestamp = int(row['timestamp_ms'])
            hex_bytes = row['hex_bytes']

            data = parse_hex_line(hex_bytes)
            record_info = identify_board_frames(data, record_num, timestamp)
            all_records.append(record_info)

    print(f"Total records parsed: {len(all_records)}")
    print()

    # Analyze frame structure from first few records
    print("=" * 80)
    print("FRAME STRUCTURE ANALYSIS")
    print("=" * 80)
    print()

    for i in range(min(10, len(all_records))):
        rec = all_records[i]
        print(f"Record {rec['record_num']} (timestamp {rec['timestamp']} ms):")
        print(f"  Frames found: {len(rec['frames'])}")
        for j, frame in enumerate(rec['frames']):
            print(f"    Frame {j+1}: status={' '.join(frame['status'])}")
            if len(frame['payload']) > 0:
                print(f"             payload={' '.join(frame['payload'])}")
        print()

    # Now let's extract payload sequences more carefully
    # Looking at the data, after each "5C C7 33", we have status then payload
    # Let's track payloads more systematically

    print("=" * 80)
    print("PAYLOAD EXTRACTION - Looking for 3 boards per cycle")
    print("=" * 80)
    print()

    # Re-analyze with better frame extraction
    payload_sequences = []

    for row_idx, row in enumerate(all_records[:20]):
        print(f"\nRecord {row['record_num']}:")

        # Manually parse to find all 5C C7 33 sequences
        raw_data = []
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for i, r in enumerate(reader):
                if i == row_idx:
                    raw_data = parse_hex_line(r['hex_bytes'])
                    break

        sync_pos = find_sync_headers(raw_data)
        print(f"  Found {len(sync_pos)} sync headers at positions: {sync_pos}")

        for sp_idx, sp in enumerate(sync_pos):
            # After sync (3 bytes), extract next 24 bytes to see pattern
            extract_end = min(sp + 27, len(raw_data))
            segment = raw_data[sp:extract_end]
            print(f"    Sync {sp_idx+1} @ pos {sp}: {' '.join(segment)}")

    # Track state changes across records
    print("\n" + "=" * 80)
    print("STATE TRANSITION TRACKING")
    print("=" * 80)
    print()

    # Let's focus on extracting the actual payload blocks
    # Pattern seems to be: 5C C7 33 [status ~8 bytes] [payload 16 bytes]

    board_payloads = {1: [], 2: [], 3: []}

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_data = parse_hex_line(row['hex_bytes'])
            sync_pos = find_sync_headers(raw_data)

            record_boards = []
            for sp in sync_pos:
                # Skip sync header (3 bytes)
                # Status appears to be 8 bytes
                # Payload is next 16 bytes
                payload_start = sp + 11  # 3 (sync) + 8 (status)
                payload_end = payload_start + 16

                if payload_end <= len(raw_data):
                    payload = raw_data[payload_start:payload_end]
                    # Check if this looks like a valid payload (not another sync header)
                    if payload[:3] != SYNC_HEADER:
                        record_boards.append(payload)

            # We expect up to 3 boards per record
            for board_num in range(min(3, len(record_boards))):
                board_payloads[board_num + 1].append({
                    'record': int(row['record_num']),
                    'timestamp': int(row['timestamp_ms']),
                    'payload': record_boards[board_num]
                })

    # Print first few payloads for each board
    print("First 20 payload blocks per board:")
    for board in [1, 2, 3]:
        print(f"\nBoard {board}:")
        for i in range(min(20, len(board_payloads[board]))):
            p = board_payloads[board][i]
            print(f"  Rec {p['record']:3d}: {' '.join(p['payload'])}")

    # Now analyze byte-by-byte changes
    print("\n" + "=" * 80)
    print("BYTE-LEVEL CHANGE DETECTION")
    print("=" * 80)
    print()

    # Track which bytes change and when
    for board in [1, 2, 3]:
        print(f"\nBoard {board} - Tracking changes in each payload position:")

        if len(board_payloads[board]) < 2:
            continue

        # Track unique values at each position
        position_values = defaultdict(set)

        for p in board_payloads[board]:
            payload = p['payload']
            for pos in range(len(payload)):
                if pos < 16:  # We expect 16-byte payloads
                    position_values[pos].add(payload[pos] if pos < len(payload) else 'XX')

        # Print positions that have variations
        print(f"  Positions with value variations:")
        for pos in sorted(position_values.keys()):
            values = sorted(position_values[pos])
            if len(values) > 1:
                print(f"    Pos {pos:2d}: {values} ({len(values)} unique values)")

    # Detailed state transition analysis
    print("\n" + "=" * 80)
    print("DETAILED STATE TRANSITION ANALYSIS")
    print("=" * 80)
    print()

    # For each channel, track state changes
    # Board 1: channels 1-16 (payload positions 0-15)
    # Board 2: channels 17-32 (payload positions 0-15)
    # Board 3: channels 33-40 (payload positions 0-7)

    channel_states = {}
    for ch in range(1, 41):
        channel_states[ch] = []

    # Map channels to board and position
    for p in board_payloads[1]:
        for pos in range(16):
            ch = pos + 1
            if pos < len(p['payload']):
                channel_states[ch].append({
                    'record': p['record'],
                    'timestamp': p['timestamp'],
                    'value': p['payload'][pos]
                })

    for p in board_payloads[2]:
        for pos in range(16):
            ch = pos + 17
            if pos < len(p['payload']):
                channel_states[ch].append({
                    'record': p['record'],
                    'timestamp': p['timestamp'],
                    'value': p['payload'][pos]
                })

    for p in board_payloads[3]:
        for pos in range(8):  # Only 8 channels on board 3
            ch = pos + 33
            if pos < len(p['payload']):
                channel_states[ch].append({
                    'record': p['record'],
                    'timestamp': p['timestamp'],
                    'value': p['payload'][pos]
                })

    # Find transitions for each channel
    print("Channel state transitions (first transition for each channel):")
    print()

    for ch in range(1, 41):
        states = channel_states[ch]
        if len(states) < 2:
            continue

        # Find first significant transition
        prev_val = states[0]['value']
        transition_found = False

        for i in range(1, len(states)):
            curr_val = states[i]['value']
            if curr_val != prev_val:
                print(f"Channel {ch:2d}: {prev_val} -> {curr_val} @ record {states[i]['record']}")
                transition_found = True
                prev_val = curr_val
                # Show next few transitions too
                transition_count = 1
                for j in range(i+1, min(i+5, len(states))):
                    if states[j]['value'] != prev_val:
                        print(f"           : {prev_val} -> {states[j]['value']} @ record {states[j]['record']}")
                        prev_val = states[j]['value']
                        transition_count += 1
                break

        if not transition_found:
            print(f"Channel {ch:2d}: No transitions (constant {prev_val})")

    # Summary of unique values per channel
    print("\n" + "=" * 80)
    print("CHANNEL VALUE SUMMARY")
    print("=" * 80)
    print()

    for ch in range(1, 41):
        unique_vals = set(s['value'] for s in channel_states[ch])
        print(f"Channel {ch:2d}: {sorted(unique_vals)}")

    return channel_states, board_payloads

if __name__ == '__main__':
    channel_states, board_payloads = analyze_capture_file('/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv')
