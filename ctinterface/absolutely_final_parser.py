#!/usr/bin/env python3
"""
ABSOLUTELY FINAL CORRECT CT2 Protocol Parser

After careful analysis, the frame structure is:
  Second frame in each record:
    5C C7 33 | 35 5A 35 [variant] | [8 channel bytes] | [4 checksum bytes]
    Where variant is typically 65, but can be other values like 35

The 8 channel bytes immediately follow the variant byte.
Position depends on variant byte value.
"""

import csv
from collections import defaultdict

def parse_hex(s):
    return s.strip().split()

SYNC_HEADER = ['5C', 'C7', '33']

def extract_channel_frames(filename):
    """
    Extract channel data from second sync header in each record.
    Pattern: 5C C7 33 35 5A 35 [var] [8 channels] [4 checksum]
    """

    frames = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec_num = int(row['record_num'])
            elapsed = int(row['elapsed_ms'])
            data = parse_hex(row['hex_bytes'])

            # Find all sync headers
            syncs = []
            for i in range(len(data) - 2):
                if data[i:i+3] == SYNC_HEADER:
                    syncs.append(i)

            # We want the SECOND sync header (or first if only one exists)
            if len(syncs) >= 2:
                pos = syncs[1]
            elif len(syncs) == 1:
                pos = syncs[0]
            else:
                continue

            # Check for pattern: 5C C7 33 35 5A 35 [variant]
            if (pos + 6 < len(data) and
                data[pos] == '5C' and
                data[pos+1] == 'C7' and
                data[pos+2] == '33' and
                data[pos+3] == '35' and
                data[pos+4] == '5A' and
                data[pos+5] == '35'):

                # Found the pattern!
                variant = data[pos+6] if pos+6 < len(data) else None

                # Channel data starts at pos+7
                channel_start = pos + 7
                channel_end = channel_start + 8

                if channel_end <= len(data):
                    channels = data[channel_start:channel_end]

                    # Checksum is next 4 bytes
                    checksum = []
                    if channel_end + 4 <= len(data):
                        checksum = data[channel_end:channel_end+4]

                    frames.append({
                        'record': rec_num,
                        'elapsed': elapsed,
                        'variant': variant,
                        'channels': channels,
                        'checksum': checksum
                    })

    return frames

def analyze_channels(frames):
    """
    Extract channel history.
    Each frame has 8 channels.
    Assuming these are board 1 (channels 1-8) cycling through records.
    """

    channel_history = defaultdict(list)

    for frame in frames:
        for pos in range(8):
            if pos < len(frame['channels']):
                ch = pos + 1  # Channels 1-8
                channel_history[ch].append({
                    'record': frame['record'],
                    'elapsed': frame['elapsed'],
                    'value': frame['channels'][pos]
                })

    return channel_history

def print_analysis(channel_history):
    """Print comprehensive analysis."""

    print("=" * 100)
    print("CHANNEL ANALYSIS")
    print("=" * 100)
    print()

    print(f"{'Ch':<4} {'Unique Values':<40} {'#Rec':<6} {'#Trans':<7} {'First Transition':<30}")
    print("-" * 100)

    state_info = {}

    for ch in range(1, 9):
        if ch not in channel_history:
            print(f"{ch:<4} {'NO DATA':<40}")
            continue

        history = channel_history[ch]
        unique_vals = sorted(set(h['value'] for h in history))

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

        unique_str = ' '.join(unique_vals[:10])
        if len(unique_vals) > 10:
            unique_str += ' ...'

        trans_str = ""
        if transitions:
            t = transitions[0]
            trans_str = f"{t['from']}->{t['to']} @rec{t['record']}"

        print(f"{ch:<4} {unique_str:<40} {len(history):<6} {len(transitions):<7} {trans_str:<30}")

        state_info[ch] = {
            'unique_values': unique_vals,
            'transitions': transitions
        }

    return state_info

def print_detailed(channel_history):
    """Print detailed record-by-record for all channels."""

    print("\n" + "=" * 100)
    print("DETAILED RECORD-BY-RECORD ANALYSIS")
    print("=" * 100)

    for ch in range(1, 9):
        if ch not in channel_history:
            continue

        print(f"\n{'='*80}")
        print(f"CHANNEL {ch}")
        print(f"{'='*80}")

        history = channel_history[ch]

        print(f"\n{'Rec':<6} {'Elapsed(ms)':<12} {'Value':<8} {'Transition':<40}")
        print("-" * 80)

        prev_val = None
        shown = 0
        for h in history:
            trans_note = ""
            if prev_val is not None and h['value'] != prev_val:
                trans_note = f"*** {prev_val} -> {h['value']}"

            print(f"{h['record']:<6} {h['elapsed']:<12} {h['value']:<8} {trans_note:<40}")
            prev_val = h['value']
            shown += 1
            if shown >= 60:  # Show first 60 records
                if len(history) > 60:
                    print(f"... ({len(history) - 60} more records)")
                break

        # Value statistics
        value_counts = defaultdict(int)
        for h in history:
            value_counts[h['value']] += 1

        print(f"\nValue Statistics (total {len(history)} records):")
        for val in sorted(value_counts.keys()):
            count = value_counts[val]
            pct = (count / len(history)) * 100
            print(f"  {val}: {count:4d} occurrences ({pct:5.1f}%)")

def build_lookup_table(state_info):
    """Build state lookup table."""

    print("\n" + "=" * 100)
    print("STATE LOOKUP TABLE FOR CHANNELS 1-8")
    print("=" * 100)
    print()

    print("For systematic test (OFF -> AUTO -> OFF pattern):\n")

    print(f"{'Channel':<10} {'OFF State':<12} {'AUTO State':<12} {'Notes':<40}")
    print("-" * 100)

    for ch in range(1, 9):
        if ch not in state_info:
            print(f"{ch:<10} {'N/A':<12} {'N/A':<12} {'No data':<40}")
            continue

        info = state_info[ch]
        unique_vals = info['unique_values']
        transitions = info['transitions']

        if len(unique_vals) == 1:
            print(f"{ch:<10} {'?':<12} {'?':<12} {f'Constant: {unique_vals[0]}':<40}")

        elif len(unique_vals) == 2:
            val1, val2 = unique_vals

            if len(transitions) >= 2:
                first_from = transitions[0]['from']
                first_to = transitions[0]['to']

                # Check for alternating pattern
                if transitions[1]['to'] == first_from:
                    print(f"{ch:<10} {first_from:<12} {first_to:<12} {'Alternating pattern (HIGH confidence)':<40}")
                else:
                    print(f"{ch:<10} {val1:<12} {val2:<12} {'Non-alternating (MEDIUM confidence)':<40}")
            else:
                print(f"{ch:<10} {val1:<12} {val2:<12} {f'{len(transitions)} transition(s) (LOW confidence)':<40}")

        else:
            print(f"{ch:<10} {'Complex':<12} {'Complex':<12} {f'{len(unique_vals)} unique values':<40}")

def main():
    filename = '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.csv'

    print("=" * 100)
    print("CT2 PROTOCOL FINAL ANALYSIS - Channels 1-8")
    print("=" * 100)
    print()

    # Extract frames
    print("Extracting channel frames from second sync header...")
    frames = extract_channel_frames(filename)
    print(f"Found {len(frames)} frames\n")

    # Show first 30
    print("First 30 frames:")
    print(f"{'#':<4} {'Rec':<6} {'Elapsed':<10} {'Variant':<8} {'Channels (1-8)':<50} {'Checksum':<20}")
    print("-" * 100)

    for i, frame in enumerate(frames[:30]):
        ch_str = ' '.join(frame['channels'])
        ck_str = ' '.join(frame['checksum'])
        print(f"{i+1:<4} {frame['record']:<6} {frame['elapsed']:<10} {frame['variant']:<8} {ch_str:<50} {ck_str:<20}")

    # Analyze channels
    print("\n" + "=" * 100)
    print("EXTRACTING CHANNEL HISTORIES")
    print("=" * 100)
    print()

    channel_history = analyze_channels(frames)
    print(f"Extracted history for {len(channel_history)} channels\n")

    # Analysis
    state_info = print_analysis(channel_history)

    # Detailed
    print_detailed(channel_history)

    # Lookup table
    build_lookup_table(state_info)

    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()
