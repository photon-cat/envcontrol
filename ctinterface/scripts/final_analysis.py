#!/usr/bin/env python3
"""
Final CT2 Protocol Analysis - Focus on actual 16-byte payload blocks.

Looking at the raw data more carefully:
- Each record typically has 2-3 sync headers (5C C7 33)
- The SECOND sync header seems to be followed by the actual 16-byte payload
- Pattern: 5C C7 33 [status] [16 payload bytes] [checksum]

Let's extract just the clean 16-byte payload blocks that don't contain sync headers.
"""

import csv
from collections import defaultdict

SYNC_HEADER = ['5C', 'C7', '33']

def parse_hex_line(hex_bytes: str):
    """Parse hex bytes string into list of hex values."""
    return hex_bytes.strip().split()

def contains_sync_header(data):
    """Check if data contains sync header."""
    for i in range(len(data) - 2):
        if data[i:i+3] == SYNC_HEADER:
            return True
    return False

def extract_payload_blocks(filename):
    """
    Extract actual 16-byte payload blocks.
    Looking at the pattern, after status blocks, we get actual 16-byte payloads
    that represent channel states.
    """

    all_payloads = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_num = int(row['record_num'])
            elapsed = int(row['elapsed_ms'])
            hex_bytes = parse_hex_line(row['hex_bytes'])

            # Find all sync headers
            i = 0
            while i < len(hex_bytes) - 2:
                if hex_bytes[i:i+3] == SYNC_HEADER:
                    # Found sync header at position i
                    # After sync (3 bytes) + status (8 bytes) = position i + 11
                    # Then we expect 16 bytes of payload

                    payload_start = i + 11
                    payload_end = payload_start + 16

                    if payload_end <= len(hex_bytes):
                        payload_candidate = hex_bytes[payload_start:payload_end]

                        # Check if this payload contains another sync header
                        # If it does, it's not a real payload
                        if not contains_sync_header(payload_candidate):
                            # This looks like a real 16-byte payload
                            all_payloads.append({
                                'record': record_num,
                                'elapsed': elapsed,
                                'sync_pos': i,
                                'payload': payload_candidate
                            })

                    # Move past this frame
                    i = payload_end
                else:
                    i += 1

    return all_payloads

def group_payloads_by_board(payloads):
    """
    Group payloads into 3 boards based on pattern.
    Assumption: payloads cycle through boards 1, 2, 3 repeatedly.
    """

    board_payloads = {1: [], 2: [], 3: []}

    # Simple cycling: every 3 payloads is one complete set
    board_idx = 0
    for payload in payloads:
        board_num = (board_idx % 3) + 1
        board_payloads[board_num].append(payload)
        board_idx += 1

    return board_payloads

def analyze_channel_states(board_payloads):
    """
    Extract channel states from board payloads.
    Board 1: channels 1-16 (payload bytes 0-15)
    Board 2: channels 17-32 (payload bytes 0-15)
    Board 3: channels 33-40 (payload bytes 0-7, bytes 8-15 might be checksum/other)
    """

    channel_history = defaultdict(list)

    # Board 1: channels 1-16
    for p in board_payloads[1]:
        for pos in range(16):
            ch = pos + 1
            channel_history[ch].append({
                'record': p['record'],
                'elapsed': p['elapsed'],
                'value': p['payload'][pos]
            })

    # Board 2: channels 17-32
    for p in board_payloads[2]:
        for pos in range(16):
            ch = pos + 17
            channel_history[ch].append({
                'record': p['record'],
                'elapsed': p['elapsed'],
                'value': p['payload'][pos]
            })

    # Board 3: channels 33-40 (only first 8 bytes)
    for p in board_payloads[3]:
        for pos in range(8):
            ch = pos + 33
            channel_history[ch].append({
                'record': p['record'],
                'elapsed': p['elapsed'],
                'value': p['payload'][pos]
            })

    return channel_history

def find_baseline_states(channel_history):
    """
    Identify baseline (idle) states for each channel.
    The systematic test goes: OFF -> AUTO -> OFF -> AUTO...
    So the most common value or the initial value is likely one of these states.
    """

    print("=" * 80)
    print("CHANNEL BASELINE STATE IDENTIFICATION")
    print("=" * 80)
    print()

    baseline_lookup = {}

    for ch in range(1, 41):
        history = channel_history[ch]
        if not history:
            continue

        # Count value frequencies
        value_counts = defaultdict(int)
        for h in history:
            value_counts[h['value']] += 1

        # Sort by frequency
        sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)

        # Get first few values in the timeline
        first_values = [history[i]['value'] for i in range(min(10, len(history)))]

        # Find unique values
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

        baseline_lookup[ch] = {
            'unique_values': unique_values,
            'most_common': sorted_values[0][0] if sorted_values else None,
            'first_value': history[0]['value'],
            'transitions': transitions[:5],  # First 5 transitions
            'value_counts': dict(sorted_values)
        }

    # Print summary
    print(f"{'Ch':<4} {'Unique Values':<35} {'Most Common':<12} {'First Val':<10} {'Transitions':<30}")
    print("-" * 100)

    for ch in range(1, 41):
        if ch not in baseline_lookup:
            continue

        lookup = baseline_lookup[ch]
        unique_str = ' '.join(lookup['unique_values'][:8])  # First 8 unique values
        if len(lookup['unique_values']) > 8:
            unique_str += '...'

        most_common = lookup['most_common']
        first_val = lookup['first_value']

        trans_str = ""
        if lookup['transitions']:
            t = lookup['transitions'][0]
            trans_str = f"{t['from']}->{t['to']} @{t['record']}"

        print(f"{ch:<4} {unique_str:<35} {most_common:<12} {first_val:<10} {trans_str:<30}")

    return baseline_lookup

def detailed_transition_analysis(channel_history, target_channels):
    """
    Detailed analysis of specific channels to understand state patterns.
    """

    print("\n" + "=" * 80)
    print("DETAILED TRANSITION ANALYSIS (Selected Channels)")
    print("=" * 80)
    print()

    for ch in target_channels:
        if ch not in channel_history:
            continue

        print(f"\n{'='*60}")
        print(f"Channel {ch}")
        print(f"{'='*60}")

        history = channel_history[ch]

        # Show first 30 records with transitions marked
        print(f"\nFirst 30 records:")
        print(f"{'Rec':<6} {'Elapsed':<10} {'Value':<6} {'Note':<30}")
        print("-" * 60)

        prev_val = None
        for i in range(min(30, len(history))):
            h = history[i]
            note = ""
            if prev_val is not None and h['value'] != prev_val:
                note = f"TRANSITION: {prev_val} -> {h['value']}"

            print(f"{h['record']:<6} {h['elapsed']:<10} {h['value']:<6} {note:<30}")
            prev_val = h['value']

        # Value statistics
        value_counts = defaultdict(int)
        for h in history:
            value_counts[h['value']] += 1

        print(f"\nValue Statistics:")
        for val, count in sorted(value_counts.items()):
            percentage = (count / len(history)) * 100
            print(f"  {val}: {count} occurrences ({percentage:.1f}%)")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

    print("=" * 80)
    print("CT2 PROTOCOL PAYLOAD ANALYSIS")
    print("Systematic Test: Channels 1-40, OFF->AUTO->OFF, then all AUTO")
    print("=" * 80)
    print()

    # Extract payload blocks
    print("Extracting payload blocks...")
    payloads = extract_payload_blocks(filename)
    print(f"Found {len(payloads)} payload blocks\n")

    # Show first few payloads
    print("First 10 payload blocks:")
    for i, p in enumerate(payloads[:10]):
        print(f"  {i+1}. Rec {p['record']:3d} @ {p['elapsed']:6d}ms: {' '.join(p['payload'])}")

    # Group by board
    print("\n" + "=" * 80)
    print("GROUPING PAYLOADS BY BOARD")
    print("=" * 80)
    print()

    board_payloads = group_payloads_by_board(payloads)
    for board in [1, 2, 3]:
        print(f"\nBoard {board}: {len(board_payloads[board])} payloads")
        print("  First 5:")
        for p in board_payloads[board][:5]:
            print(f"    Rec {p['record']:3d}: {' '.join(p['payload'])}")

    # Analyze channel states
    print("\n" + "=" * 80)
    print("EXTRACTING CHANNEL STATES")
    print("=" * 80)
    print()

    channel_history = analyze_channel_states(board_payloads)

    print(f"Extracted state history for {len(channel_history)} channels")

    # Identify baseline states
    baseline_lookup = find_baseline_states(channel_history)

    # Detailed analysis of selected channels (one from each board)
    print("\n" + "=" * 80)
    print("DETAILED ANALYSIS")
    print("=" * 80)

    # Analyze channels 1, 17, 33 as representatives of each board
    detailed_transition_analysis(channel_history, [1, 10, 14, 17, 22, 33, 38])

    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY: STATE VALUE IDENTIFICATION")
    print("=" * 80)
    print()

    print("Based on the systematic test pattern (OFF -> AUTO -> OFF -> ... -> all AUTO),")
    print("we can identify the byte values for each state:\n")

    print(f"{'Channel':<8} {'Primary States':<40} {'Notes':<30}")
    print("-" * 80)

    for ch in range(1, 41):
        if ch not in baseline_lookup:
            continue

        lookup = baseline_lookup[ch]
        unique_vals = lookup['unique_values']

        if len(unique_vals) == 1:
            print(f"{ch:<8} {unique_vals[0]:<40} {'No transitions (constant)':<30}")
        elif len(unique_vals) == 2:
            # Most likely: one is OFF, one is AUTO
            print(f"{ch:<8} {unique_vals[0]} (OFF?), {unique_vals[1]} (AUTO?) {'':<30}")
        else:
            # Multiple values - more complex
            vals_str = ', '.join(unique_vals[:5])
            if len(unique_vals) > 5:
                vals_str += ', ...'
            print(f"{ch:<8} {vals_str:<40} {f'{len(unique_vals)} states':<30}")

if __name__ == '__main__':
    main()
