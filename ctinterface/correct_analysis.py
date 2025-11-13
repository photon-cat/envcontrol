#!/usr/bin/env python3
"""
Correct CT2 Protocol Analysis based on discovered frame structure.

Frame Structure (from analysis):
- Pattern appears regularly: 5C C7 33 35 5A 35 [variant byte] 65 [8 channel bytes] [4 checksum bytes]
- OR: 5C C7 33 35 5A 35 35 65 [8 channel bytes] [4 checksum bytes]

The "35 5A 35 65" pattern is followed by:
- 8 bytes of channel data
- 4 bytes of checksum/trailer

So each "payload block" represents 8 channels, not 16.

For 40 channels, we need 5 payload blocks (5 × 8 = 40 channels).
"""

import csv
from collections import defaultdict

def parse_hex(s):
    return s.strip().split()

def extract_channel_payloads(filename):
    """
    Extract 8-byte channel payloads that follow the pattern "35 5A 35 65" or "35 5A 35 35 65"
    """

    all_payloads = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec_num = int(row['record_num'])
            elapsed = int(row['elapsed_ms'])
            data = parse_hex(row['hex_bytes'])

            # Look for pattern: 35 5A 35 [xx] 65
            # where xx is typically 65 or 35
            i = 0
            while i < len(data) - 12:  # Need at least 4 (pattern) + 8 (channels) + 4 (checksum) = 16 bytes
                if (data[i:i+3] == ['35', '5A', '35'] and
                    i + 4 < len(data) and data[i+4] == '65'):

                    # Found pattern at position i
                    # Extract 8 channel bytes starting at i+5
                    payload_start = i + 5
                    payload_end = payload_start + 8

                    if payload_end <= len(data):
                        channel_bytes = data[payload_start:payload_end]

                        # Also get the 4 checksum bytes
                        checksum = []
                        if payload_end + 4 <= len(data):
                            checksum = data[payload_end:payload_end+4]

                        all_payloads.append({
                            'record': rec_num,
                            'elapsed': elapsed,
                            'pos': i,
                            'variant': data[i+3],  # The byte between 35 5A 35 [X] 65
                            'channels': channel_bytes,
                            'checksum': checksum
                        })

                    # Move past this payload
                    i = payload_end + 4
                else:
                    i += 1

    return all_payloads

def group_payloads_by_board(payloads):
    """
    Group 8-channel payloads into boards.
    Assuming 5 boards for 40 channels total (8 channels × 5 = 40).
    """

    # Pattern: payloads cycle through boards repeatedly
    board_payloads = defaultdict(list)

    board_count = 5  # For 40 channels
    for idx, payload in enumerate(payloads):
        board_num = (idx % board_count) + 1
        board_payloads[board_num].append(payload)

    return board_payloads

def analyze_channel_transitions(board_payloads):
    """
    Extract channel state history.
    Board 1: channels 1-8
    Board 2: channels 9-16
    Board 3: channels 17-24
    Board 4: channels 25-32
    Board 5: channels 33-40
    """

    channel_history = defaultdict(list)

    for board_num in range(1, 6):
        if board_num not in board_payloads:
            continue

        for payload in board_payloads[board_num]:
            channels = payload['channels']
            base_channel = (board_num - 1) * 8 + 1

            for pos in range(min(8, len(channels))):
                ch = base_channel + pos
                channel_history[ch].append({
                    'record': payload['record'],
                    'elapsed': payload['elapsed'],
                    'value': channels[pos]
                })

    return channel_history

def identify_state_values(channel_history):
    """
    For each channel, identify the byte values that correspond to different states.
    Based on systematic test: OFF -> AUTO -> OFF -> AUTO ... -> all AUTO
    """

    print("=" * 80)
    print("CHANNEL STATE VALUE IDENTIFICATION")
    print("=" * 80)
    print()

    print(f"{'Ch':<4} {'Unique Values':<30} {'#Trans':<7} {'First Transition':<30}")
    print("-" * 80)

    state_info = {}

    for ch in range(1, 41):
        if ch not in channel_history:
            print(f"{ch:<4} {'No data':<30}")
            continue

        history = channel_history[ch]
        unique_values = sorted(set(h['value'] for h in history))

        # Find transitions
        transitions = []
        if len(history) > 1:
            prev = history[0]['value']
            for i in range(1, len(history)):
                if history[i]['value'] != prev:
                    transitions.append({
                        'from': prev,
                        'to': history[i]['value'],
                        'record': history[i]['record'],
                        'elapsed': history[i]['elapsed']
                    })
                    prev = history[i]['value']

        # Format unique values
        unique_str = ' '.join(unique_values[:6])
        if len(unique_values) > 6:
            unique_str += ' ...'

        # First transition info
        trans_str = ""
        if transitions:
            t = transitions[0]
            trans_str = f"{t['from']}->{t['to']} @rec{t['record']}"

        print(f"{ch:<4} {unique_str:<30} {len(transitions):<7} {trans_str:<30}")

        state_info[ch] = {
            'unique_values': unique_values,
            'transitions': transitions,
            'first_value': history[0]['value']
        }

    return state_info

def detailed_channel_analysis(channel_history, channels_to_analyze):
    """
    Show detailed transition analysis for specific channels.
    """

    print("\n" + "=" * 80)
    print("DETAILED CHANNEL TRANSITION ANALYSIS")
    print("=" * 80)

    for ch in channels_to_analyze:
        if ch not in channel_history:
            continue

        print(f"\n{'='*60}")
        print(f"Channel {ch}")
        print(f"{'='*60}")

        history = channel_history[ch]

        # Show first 40 records with transitions highlighted
        print(f"\nFirst 40 records:")
        print(f"{'Rec':<6} {'Elapsed(ms)':<12} {'Value':<6} {'Note':<30}")
        print("-" * 60)

        prev_val = None
        for i in range(min(40, len(history))):
            h = history[i]
            note = ""
            if prev_val is not None and h['value'] != prev_val:
                note = f"*** CHANGE: {prev_val} -> {h['value']}"

            print(f"{h['record']:<6} {h['elapsed']:<12} {h['value']:<6} {note:<30}")
            prev_val = h['value']

        # Count value occurrences
        value_counts = defaultdict(int)
        for h in history:
            value_counts[h['value']] += 1

        print(f"\nValue Statistics (total {len(history)} records):")
        for val in sorted(value_counts.keys()):
            count = value_counts[val]
            pct = (count / len(history)) * 100
            print(f"  {val}: {count:4d} occurrences ({pct:5.1f}%)")

def build_state_lookup_table(channel_history, state_info):
    """
    Build a lookup table mapping byte values to states (OFF, AUTO_IDLE, AUTO_ON).
    """

    print("\n" + "=" * 80)
    print("STATE LOOKUP TABLE")
    print("=" * 80)
    print()

    print("Based on the systematic test pattern (channels toggled OFF->AUTO->OFF),")
    print("we can infer the meaning of byte values:\n")

    print(f"{'Ch':<4} {'OFF':<6} {'AUTO':<6} {'Other Values':<30} {'Confidence':<15}")
    print("-" * 80)

    for ch in range(1, 41):
        if ch not in state_info:
            print(f"{ch:<4} {'N/A':<6} {'N/A':<6} {'':<30} {'No data':<15}")
            continue

        info = state_info[ch]
        unique_vals = info['unique_values']
        transitions = info['transitions']

        if len(unique_vals) == 1:
            # No transitions - constant value (might be unused channel)
            print(f"{ch:<4} {'?':<6} {'?':<6} {unique_vals[0]:<30} {'Constant':<15}")
        elif len(unique_vals) == 2:
            # Two states - likely OFF and AUTO_IDLE
            # The test goes OFF->AUTO->OFF, so we need to identify which is which
            # Look at the transition pattern
            if len(transitions) >= 2:
                # First transition might be OFF->AUTO
                first_val = transitions[0]['from']
                second_val = transitions[0]['to']

                # If it alternates back, we have OFF<->AUTO pattern
                if transitions[1]['to'] == first_val:
                    # Alternating pattern
                    print(f"{ch:<4} {first_val:<6} {second_val:<6} {'':<30} {'High (2-state)':<15}")
                else:
                    print(f"{ch:<4} {first_val:<6} {second_val:<6} {'':<30} {'Medium':<15}")
            else:
                # Single transition
                print(f"{ch:<4} {unique_vals[0]:<6} {unique_vals[1]:<6} {'':<30} {'Low (1 trans)':<15}")
        else:
            # More than 2 states - complex
            main_states = ' '.join(unique_vals[:4])
            other_states = ' '.join(unique_vals[4:]) if len(unique_vals) > 4 else ''
            print(f"{ch:<4} {'?':<6} {'?':<6} {main_states:<30} {f'{len(unique_vals)} states':<15}")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

    print("=" * 80)
    print("CT2 PROTOCOL ANALYSIS - Systematic Test (Channels 1-40)")
    print("=" * 80)
    print()

    # Extract payloads
    print("Extracting 8-byte channel payloads...")
    payloads = extract_channel_payloads(filename)
    print(f"Found {len(payloads)} payload blocks\n")

    # Show first few
    print("First 15 payload blocks:")
    for i, p in enumerate(payloads[:15]):
        print(f"  {i+1:2d}. Rec {p['record']:3d} @ {p['elapsed']:6d}ms: {' '.join(p['channels'])} | cksum: {' '.join(p['checksum'])}")

    # Group by board
    print("\n" + "=" * 80)
    print("GROUPING BY BOARD (assuming 5 boards × 8 channels = 40 channels)")
    print("=" * 80)
    print()

    board_payloads = group_payloads_by_board(payloads)
    for board in range(1, 6):
        print(f"\nBoard {board} (channels {(board-1)*8+1}-{board*8}): {len(board_payloads[board])} payloads")
        print("  First 5:")
        for p in list(board_payloads[board])[:5]:
            print(f"    Rec {p['record']:3d}: {' '.join(p['channels'])}")

    # Analyze channel transitions
    print("\n" + "=" * 80)
    print("EXTRACTING CHANNEL STATE HISTORY")
    print("=" * 80)
    print()

    channel_history = analyze_channel_transitions(board_payloads)
    print(f"Extracted history for {len(channel_history)} channels\n")

    # Identify state values
    state_info = identify_state_values(channel_history)

    # Detailed analysis of selected channels
    detailed_channel_analysis(channel_history, [1, 5, 10, 15, 20, 25, 30, 35, 40])

    # Build lookup table
    build_state_lookup_table(channel_history, state_info)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
