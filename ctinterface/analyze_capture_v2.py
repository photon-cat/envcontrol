#!/usr/bin/env python3
"""
Improved CT2 protocol capture analyzer.
Correctly parse frame structure: 5C C7 33 [8 status bytes] [16 payload bytes]
"""

import csv
from collections import defaultdict
from typing import List, Dict, Tuple

SYNC_HEADER = ['5C', 'C7', '33']

def parse_hex_line(hex_bytes: str) -> List[str]:
    """Parse hex bytes string into list of hex values."""
    return hex_bytes.strip().split()

def extract_all_frames_from_capture(filename: str) -> List[Dict]:
    """
    Extract all frames from the entire capture file.
    Each frame: 5C C7 33 [8 bytes status] [16 bytes payload]
    Returns list of frames with metadata.
    """
    frames = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            timestamp = int(row['timestamp_ms'])
            elapsed = int(row['elapsed_ms'])
            hex_bytes = parse_hex_line(row['hex_bytes'])

            # Find all sync headers in this record
            i = 0
            while i < len(hex_bytes) - 2:
                if hex_bytes[i:i+3] == SYNC_HEADER:
                    # Found sync header
                    sync_pos = i

                    # Status is next 8 bytes
                    status_start = i + 3
                    status_end = status_start + 8

                    # Payload is next 16 bytes after status
                    payload_start = status_end
                    payload_end = payload_start + 16

                    # Extract if we have enough bytes
                    if status_end <= len(hex_bytes):
                        status = hex_bytes[status_start:status_end]

                        # Check for payload
                        payload = []
                        if payload_end <= len(hex_bytes):
                            payload = hex_bytes[payload_start:payload_end]
                        elif payload_start < len(hex_bytes):
                            # Partial payload
                            payload = hex_bytes[payload_start:]

                        frames.append({
                            'record_num': record_num,
                            'timestamp': timestamp,
                            'elapsed': elapsed,
                            'sync_pos': sync_pos,
                            'status': status,
                            'payload': payload
                        })

                    # Move past this frame (sync + status + payload)
                    i = payload_end
                else:
                    i += 1

    return frames

def identify_board_type(status: List[str]) -> int:
    """
    Identify which board (1, 2, or 3) based on status bytes.
    Looking at the pattern:
    - Status byte 0 alternates between 35 and 56 (might be board ID or sequence)
    - Status byte 1: 96 or 56 (varies)

    Let's use a heuristic: the order in typical records is Board1, Board2, Board3
    """
    # Simple heuristic - will refine based on data
    # For now, track by sequence number within each logical group
    if len(status) >= 2:
        # Board identification based on status pattern
        b0 = status[0]
        b1 = status[1]

        # Pattern observed:
        # Board 1: usually starts with 35 96 or 56 56
        # Board 2: similar pattern
        # Board 3: similar pattern
        # They cycle through records

        # For now, return -1 (unknown), we'll identify by position
        return -1
    return -1

def analyze_frames_by_cycle(frames: List[Dict]):
    """
    Analyze frames organized by transmission cycle.
    Each cycle typically has 3 frames (boards 1, 2, 3).
    """

    print("=" * 80)
    print("FRAME CYCLE ANALYSIS")
    print("=" * 80)
    print()

    # Group frames by logical cycles
    # Heuristic: frames within ~300ms are part of same cycle

    cycles = []
    current_cycle = []
    last_record = None

    for frame in frames:
        if last_record is None or frame['record_num'] != last_record:
            # New record - might be new cycle or continuation
            # Check if we should start a new cycle
            if len(current_cycle) >= 3:
                # Complete cycle, start new one
                cycles.append(current_cycle)
                current_cycle = []

        if len(frame['payload']) >= 10:  # Only consider frames with substantial payloads
            current_cycle.append(frame)

        last_record = frame['record_num']

    # Add last cycle
    if current_cycle:
        cycles.append(current_cycle)

    print(f"Found {len(cycles)} cycles")
    print()

    # Analyze first 10 cycles
    print("First 10 cycles:")
    for i, cycle in enumerate(cycles[:10]):
        print(f"\nCycle {i+1}: {len(cycle)} frames")
        for j, frame in enumerate(cycle):
            print(f"  Frame {j+1} (rec {frame['record_num']}):")
            print(f"    Status:  {' '.join(frame['status'])}")
            print(f"    Payload: {' '.join(frame['payload'])}")

    return cycles

def extract_board_payloads(frames: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Extract payloads for each board.
    We'll use a pattern-based approach:
    - Frames cycle through 3 boards repeatedly
    - Group frames in sets of 3
    """

    # Filter frames with full payloads
    full_frames = [f for f in frames if len(f['payload']) == 16]

    board_payloads = {1: [], 2: [], 3: []}

    # Simple approach: every 3 frames is one set (board 1, 2, 3)
    for i in range(0, len(full_frames), 3):
        if i + 2 < len(full_frames):
            # Assign to boards
            for board_idx in range(3):
                frame = full_frames[i + board_idx]
                board_payloads[board_idx + 1].append({
                    'record_num': frame['record_num'],
                    'timestamp': frame['timestamp'],
                    'elapsed': frame['elapsed'],
                    'payload': frame['payload']
                })

    return board_payloads

def analyze_channel_transitions(board_payloads: Dict[int, List[Dict]]):
    """
    Analyze state transitions for each channel.
    """

    print("\n" + "=" * 80)
    print("CHANNEL STATE ANALYSIS")
    print("=" * 80)
    print()

    # Map channels to boards and payload positions
    channel_map = {}
    for ch in range(1, 17):
        channel_map[ch] = {'board': 1, 'pos': ch - 1}
    for ch in range(17, 33):
        channel_map[ch] = {'board': 2, 'pos': ch - 17}
    for ch in range(33, 41):
        channel_map[ch] = {'board': 3, 'pos': ch - 33}

    # Extract channel values over time
    channel_history = defaultdict(list)

    for ch, mapping in channel_map.items():
        board = mapping['board']
        pos = mapping['pos']

        for payload_rec in board_payloads[board]:
            if pos < len(payload_rec['payload']):
                value = payload_rec['payload'][pos]
                channel_history[ch].append({
                    'record': payload_rec['record_num'],
                    'elapsed': payload_rec['elapsed'],
                    'value': value
                })

    # Print channel summaries
    print("Channel value summaries:")
    print()

    for ch in range(1, 41):
        history = channel_history[ch]
        if not history:
            print(f"Channel {ch:2d}: No data")
            continue

        unique_values = sorted(set(h['value'] for h in history))

        # Find transitions
        transitions = []
        if len(history) > 1:
            prev_val = history[0]['value']
            for i in range(1, len(history)):
                curr_val = history[i]['value']
                if curr_val != prev_val:
                    transitions.append({
                        'from': prev_val,
                        'to': curr_val,
                        'record': history[i]['record'],
                        'elapsed': history[i]['elapsed']
                    })
                    prev_val = curr_val

        print(f"Channel {ch:2d}: Values={unique_values} ({len(unique_values)} unique)")
        if transitions:
            print(f"           First transitions:")
            for t in transitions[:3]:
                print(f"             {t['from']} -> {t['to']} @ record {t['record']} (elapsed {t['elapsed']}ms)")

    return channel_history

def identify_state_meanings(channel_history: Dict[int, List[Dict]]):
    """
    Attempt to identify what each byte value means.
    Based on systematic test: OFF -> AUTO -> OFF -> ... -> all AUTO
    """

    print("\n" + "=" * 80)
    print("STATE MEANING IDENTIFICATION")
    print("=" * 80)
    print()

    # For each channel, identify patterns
    state_lookup = {}

    for ch in range(1, 41):
        history = channel_history[ch]
        if not history or len(history) < 10:
            continue

        unique_values = sorted(set(h['value'] for h in history))

        if len(unique_values) <= 1:
            # Channel never changed - might be unused or stuck
            state_lookup[ch] = {
                'OFF': unique_values[0] if unique_values else None,
                'AUTO_IDLE': None,
                'AUTO_ON': None,
                'note': 'No transitions observed'
            }
            continue

        # Find first few values to identify baseline
        first_val = history[0]['value']

        # Find transitions
        transitions = []
        prev_val = first_val
        for i in range(1, len(history)):
            curr_val = history[i]['value']
            if curr_val != prev_val:
                transitions.append({
                    'idx': i,
                    'from': prev_val,
                    'to': curr_val,
                    'record': history[i]['record']
                })
                prev_val = curr_val

        # Pattern: starts in one state (likely OFF or AUTO idle)
        # First transition might be OFF->AUTO or AUTO->AUTO_ON
        # Look for pattern of alternating values

        if len(transitions) >= 2:
            # Check if it alternates between 2 values initially
            t1 = transitions[0]
            t2 = transitions[1]

            if t2['to'] == t1['from']:
                # Alternating pattern: likely OFF <-> AUTO idle
                state_lookup[ch] = {
                    'OFF': t1['from'],
                    'AUTO_IDLE': t1['to'],
                    'AUTO_ON': None,
                    'note': 'Alternating OFF/AUTO pattern'
                }
            else:
                # More complex pattern
                state_lookup[ch] = {
                    'values': unique_values,
                    'note': f'Complex pattern: {len(transitions)} transitions'
                }
        else:
            # Single transition
            state_lookup[ch] = {
                'value1': transitions[0]['from'],
                'value2': transitions[0]['to'],
                'note': 'Single transition observed'
            }

    # Print lookup table
    print("State Lookup Table:")
    print()
    print(f"{'Channel':<10} {'OFF':<8} {'AUTO_IDLE':<12} {'AUTO_ON':<10} {'Note':<30}")
    print("-" * 80)

    for ch in sorted(state_lookup.keys()):
        lookup = state_lookup[ch]
        off_val = lookup.get('OFF', '-')
        auto_idle = lookup.get('AUTO_IDLE', '-')
        auto_on = lookup.get('AUTO_ON', '-')
        note = lookup.get('note', '')

        if off_val == None:
            off_val = '-'
        if auto_idle == None:
            auto_idle = '-'
        if auto_on == None:
            auto_on = '-'

        print(f"{ch:<10} {str(off_val):<8} {str(auto_idle):<12} {str(auto_on):<10} {note:<30}")

    return state_lookup

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

    print("=" * 80)
    print("CT2 PROTOCOL SYSTEMATIC TEST ANALYSIS")
    print("=" * 80)
    print()

    # Extract all frames
    print("Extracting frames from capture file...")
    frames = extract_all_frames_from_capture(filename)
    print(f"Extracted {len(frames)} frames total")
    print()

    # Show frame structure
    print("Sample frame structure (first 5 frames):")
    for i, frame in enumerate(frames[:5]):
        print(f"\nFrame {i+1} (record {frame['record_num']}, {frame['elapsed']}ms):")
        print(f"  Status:  {' '.join(frame['status'])}")
        print(f"  Payload: {' '.join(frame['payload'])}")

    # Analyze cycles
    cycles = analyze_frames_by_cycle(frames)

    # Extract board payloads
    print("\n" + "=" * 80)
    print("EXTRACTING BOARD PAYLOADS")
    print("=" * 80)
    print()

    board_payloads = extract_board_payloads(frames)

    for board in [1, 2, 3]:
        print(f"\nBoard {board}: {len(board_payloads[board])} payload records")
        print(f"  First 5:")
        for i, p in enumerate(board_payloads[board][:5]):
            print(f"    Rec {p['record_num']:3d}: {' '.join(p['payload'])}")

    # Analyze channel transitions
    channel_history = analyze_channel_transitions(board_payloads)

    # Identify state meanings
    state_lookup = identify_state_meanings(channel_history)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
