#!/usr/bin/env python3
"""
FINAL CORRECT CT2 Protocol Parser

Frame Structure (confirmed from data):
  - First sync: 5C C7 33 [8 bytes status/addressing]
  - Second sync: 5C C7 33 35 5A 35 65 [8 bytes CHANNEL DATA] [4 bytes checksum]
                 ^sync^  ^4-byte hdr^ ^8 channels^           ^4-byte cksum^

The 8 channel bytes represent the state of 8 channels.
Multiple second-sync frames appear in longer records to cover all 40 channels.
"""

import csv
from collections import defaultdict

def parse_hex(s):
    return s.strip().split()

SYNC_HEADER = ['5C', 'C7', '33']

def extract_channel_frames(filename):
    """
    Extract all channel data frames.
    Look for: 5C C7 33 35 5A 35 65 [8 channel bytes] [4 checksum bytes]
    """

    channel_frames = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec_num = int(row['record_num'])
            elapsed = int(row['elapsed_ms'])
            data = parse_hex(row['hex_bytes'])

            # Find all sync headers
            i = 0
            while i < len(data) - 2:
                if data[i:i+3] == SYNC_HEADER:
                    # Check if this is a channel data frame
                    # Pattern: 5C C7 33 35 5A 35 [xx] 65 [8 channels] [4 checksum]
                    #          0  1  2  3  4  5  6   7  8-15         16-19

                    if (i + 7 < len(data) and
                        data[i+3] == '35' and
                        data[i+4] == '5A' and
                        data[i+5] == '35' and
                        data[i+7] == '65'):

                        # This is a channel data frame
                        # Extract 8 channel bytes starting at position i+8
                        channel_start = i + 8
                        channel_end = channel_start + 8

                        if channel_end <= len(data):
                            channels = data[channel_start:channel_end]

                            # Extract checksum (next 4 bytes)
                            checksum = []
                            if channel_end + 4 <= len(data):
                                checksum = data[channel_end:channel_end+4]

                            channel_frames.append({
                                'record': rec_num,
                                'elapsed': elapsed,
                                'pos': i,
                                'variant': data[i+6],  # Byte between 35 and 65
                                'channels': channels,
                                'checksum': checksum
                            })

                            # Move past this frame
                            i = channel_end + 4
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1

    return channel_frames

def group_frames_by_board(frames):
    """
    Group frames into boards based on cycling pattern.
    For 40 channels: 5 boards × 8 channels = 40
    Frames cycle through boards 1, 2, 3, 4, 5, 1, 2, 3, 4, 5, ...
    """

    board_frames = defaultdict(list)

    for idx, frame in enumerate(frames):
        board_num = (idx % 5) + 1
        board_frames[board_num].append(frame)

    return board_frames

def analyze_channels(board_frames):
    """
    Extract channel history from board frames.
    Board 1: channels 1-8
    Board 2: channels 9-16
    Board 3: channels 17-24
    Board 4: channels 25-32
    Board 5: channels 33-40
    """

    channel_history = defaultdict(list)

    for board_num in range(1, 6):
        if board_num not in board_frames:
            continue

        for frame in board_frames[board_num]:
            base_channel = (board_num - 1) * 8 + 1

            for pos in range(8):
                if pos < len(frame['channels']):
                    ch = base_channel + pos
                    channel_history[ch].append({
                        'record': frame['record'],
                        'elapsed': frame['elapsed'],
                        'value': frame['channels'][pos]
                    })

    return channel_history

def print_channel_analysis(channel_history):
    """
    Print comprehensive channel analysis.
    """

    print("=" * 100)
    print("CHANNEL STATE ANALYSIS - All 40 Channels")
    print("=" * 100)
    print()

    print(f"{'Ch':<4} {'Unique Values':<35} {'#Records':<10} {'#Trans':<7} {'First Transition':<30}")
    print("-" * 100)

    lookup_table = {}

    for ch in range(1, 41):
        if ch not in channel_history or len(channel_history[ch]) == 0:
            print(f"{ch:<4} {'NO DATA':<35} {0:<10} {0:<7} {'':<30}")
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

        # Format output
        unique_str = ' '.join(unique_values[:8])
        if len(unique_values) > 8:
            unique_str += '...'

        trans_str = ""
        if transitions:
            t = transitions[0]
            trans_str = f"{t['from']}->{t['to']} @rec{t['record']}"

        print(f"{ch:<4} {unique_str:<35} {len(history):<10} {len(transitions):<7} {trans_str:<30}")

        # Store for lookup table
        lookup_table[ch] = {
            'unique_values': unique_values,
            'transitions': transitions,
            'first_value': history[0]['value'],
            'num_records': len(history)
        }

    return lookup_table

def print_detailed_analysis(channel_history, channels_to_show):
    """
    Show detailed record-by-record analysis for specific channels.
    """

    print("\n" + "=" * 100)
    print("DETAILED RECORD-BY-RECORD ANALYSIS (Selected Channels)")
    print("=" * 100)

    for ch in channels_to_show:
        if ch not in channel_history:
            continue

        print(f"\n{'='*80}")
        print(f"CHANNEL {ch}")
        print(f"{'='*80}")

        history = channel_history[ch]

        print(f"\nTotal records: {len(history)}")
        print(f"\n{'Rec':<6} {'Elapsed(ms)':<12} {'Value':<8} {'Transition':<40}")
        print("-" * 80)

        prev_val = None
        for i, h in enumerate(history[:50]):  # Show first 50 records
            trans_note = ""
            if prev_val is not None and h['value'] != prev_val:
                trans_note = f"*** {prev_val} -> {h['value']}"

            print(f"{h['record']:<6} {h['elapsed']:<12} {h['value']:<8} {trans_note:<40}")
            prev_val = h['value']

        # Value statistics
        value_counts = defaultdict(int)
        for h in history:
            value_counts[h['value']] += 1

        print(f"\nValue Statistics:")
        for val in sorted(value_counts.keys()):
            count = value_counts[val]
            pct = (count / len(history)) * 100
            print(f"  {val}: {count:4d} occurrences ({pct:5.1f}%)")

def build_state_lookup_table(lookup_table):
    """
    Build final lookup table mapping byte values to states.
    """

    print("\n" + "=" * 100)
    print("STATE LOOKUP TABLE")
    print("=" * 100)
    print()

    print("Based on systematic testing (OFF -> AUTO -> OFF pattern):")
    print()

    print(f"{'Channel':<10} {'OFF State':<12} {'AUTO State':<12} {'Other States':<30} {'Confidence':<15}")
    print("-" * 100)

    for ch in range(1, 41):
        if ch not in lookup_table:
            print(f"{ch:<10} {'N/A':<12} {'N/A':<12} {'':<30} {'No data':<15}")
            continue

        info = lookup_table[ch]
        unique_vals = info['unique_values']
        transitions = info['transitions']

        if len(unique_vals) == 1:
            # Constant value - no state changes
            print(f"{ch:<10} {'Unknown':<12} {'Unknown':<12} {unique_vals[0]:<30} {'Constant':<15}")

        elif len(unique_vals) == 2:
            # Two states - most likely OFF and AUTO
            val1, val2 = unique_vals

            if len(transitions) >= 2:
                # Check if alternating pattern
                first_from = transitions[0]['from']
                first_to = transitions[0]['to']

                if transitions[1]['to'] == first_from:
                    # Alternating pattern: first_from <-> first_to
                    print(f"{ch:<10} {first_from:<12} {first_to:<12} {'':<30} {'High':<15}")
                else:
                    # Non-alternating
                    print(f"{ch:<10} {val1:<12} {val2:<12} {'':<30} {'Medium':<15}")
            else:
                # Only one or no transitions
                print(f"{ch:<10} {val1:<12} {val2:<12} {'':<30} {'Low':<15}")

        else:
            # More than 2 states
            others = ', '.join(unique_vals)
            print(f"{ch:<10} {'Complex':<12} {'Complex':<12} {others:<30} {f'{len(unique_vals)} states':<15}")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

    print("=" * 100)
    print("CT2 PROTOCOL COMPREHENSIVE ANALYSIS")
    print("Systematic Test: Channels 1-40, OFF->AUTO->OFF transitions, then all AUTO")
    print("=" * 100)
    print()

    # Extract channel frames
    print("Extracting channel data frames...")
    frames = extract_channel_frames(filename)
    print(f"Found {len(frames)} channel data frames\n")

    # Show first few frames
    print("First 20 frames:")
    for i, frame in enumerate(frames[:20]):
        print(f"  {i+1:2d}. Rec {frame['record']:3d} @ {frame['elapsed']:6d}ms: {' '.join(frame['channels'])} | cksum: {' '.join(frame['checksum'])}")

    # Group by board
    print("\n" + "=" * 100)
    print("GROUPING BY BOARD")
    print("=" * 100)
    print()

    board_frames = group_frames_by_board(frames)
    for board in range(1, 6):
        ch_start = (board - 1) * 8 + 1
        ch_end = board * 8
        print(f"\nBoard {board} (channels {ch_start}-{ch_end}): {len(board_frames[board])} frames")
        if len(board_frames[board]) > 0:
            print("  First 5 frames:")
            for frame in board_frames[board][:5]:
                print(f"    Rec {frame['record']:3d}: {' '.join(frame['channels'])}")

    # Analyze channels
    print("\n" + "=" * 100)
    print("EXTRACTING CHANNEL HISTORIES")
    print("=" * 100)
    print()

    channel_history = analyze_channels(board_frames)
    print(f"Extracted history for {len(channel_history)} channels\n")

    # Print analysis
    lookup_table = print_channel_analysis(channel_history)

    # Detailed analysis for selected channels
    selected_channels = [1, 5, 10, 14, 15, 20, 25, 30, 35, 40]
    print_detailed_analysis(channel_history, selected_channels)

    # Build lookup table
    build_state_lookup_table(lookup_table)

    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()
