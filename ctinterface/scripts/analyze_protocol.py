#!/usr/bin/env python3
"""
CT2 Protocol Analyzer
Analyzes captured protocol data to understand bidirectional communication
"""

import re
from collections import defaultdict, Counter
from typing import List, Dict, Tuple

def parse_log_file(filename: str) -> List[bytes]:
    """Parse log file and extract hex data frames"""
    frames = []
    with open(filename, 'r') as f:
        for line in f:
            # Extract hex data after "DATA 500k_8E1"
            match = re.search(r'DATA 500k_8E1\s+((?:[0-9A-F]{2}\s*)+)', line)
            if match:
                hex_str = match.group(1).strip()
                hex_bytes = bytes.fromhex(hex_str.replace(' ', ''))
                frames.append(hex_bytes)
    return frames

def find_sync_sequences(data: bytes) -> List[Tuple[int, int]]:
    """Find all 5C C7 33 sync sequences and their types"""
    sync_pattern = bytes([0x5C, 0xC7, 0x33])
    sequences = []
    i = 0
    while i < len(data) - 3:
        if data[i:i+3] == sync_pattern:
            if i + 4 <= len(data):
                next_byte = data[i+3]
                sequences.append((i, next_byte))
            i += 3
        else:
            i += 1
    return sequences

def extract_frames(data: bytes) -> Dict[str, List[bytes]]:
    """Extract and categorize frames by their header pattern"""
    frames = defaultdict(list)
    sync_pattern = bytes([0x5C, 0xC7, 0x33])

    i = 0
    while i < len(data):
        if data[i:i+3] == sync_pattern and i + 7 <= len(data):
            # Extract header (sync + next 4 bytes minimum)
            header = data[i:i+7]

            # Determine frame type by 4th byte pattern
            if i + 4 <= len(data):
                if data[i+3] == 0x35 and i+6 <= len(data):
                    if data[i+4] == 0x96 and data[i+5] == 0xA5:
                        # Type A: 5C C7 33 35 96 A5 ... (appears to be command)
                        if i + 11 <= len(data):
                            frames['CMD_35_96_A5'].append(data[i:i+11])
                            i += 11
                        else:
                            i += 1
                    elif data[i+4] == 0x5A and data[i+5] == 0x35:
                        # Type B: 5C C7 33 35 5A 35 ... (appears to be response/status)
                        if i + 28 <= len(data):
                            frames['STS_35_5A_35'].append(data[i:i+28])
                            i += 28
                        else:
                            i += 1
                    elif data[i+4] == 0x95 and data[i+5] == 0x35:
                        # Type C: 5C C7 33 35 95 35 ... (special frame)
                        if i + 15 <= len(data):
                            frames['SPL_35_95_35'].append(data[i:i+15])
                            i += 15
                        else:
                            i += 1
                    else:
                        i += 1
                elif data[i+3] == 0x56 and i+6 <= len(data):
                    if data[i+4] == 0x56 and data[i+5] == 0xA5:
                        # Type D: 5C C7 33 56 56 A5 ... (command variant)
                        if i + 11 <= len(data):
                            frames['CMD_56_56_A5'].append(data[i:i+11])
                            i += 11
                        else:
                            i += 1
                    elif data[i+4] == 0x96 and data[i+5] == 0xA5:
                        # Type E: 5C C7 33 56 96 A5 ... (command variant)
                        if i + 11 <= len(data):
                            frames['CMD_56_96_A5'].append(data[i:i+11])
                            i += 11
                        else:
                            i += 1
                    elif data[i+4] == 0x35 and data[i+5] == 0x35:
                        # Type F: 5C C7 33 56 35 35 ... (special frame)
                        if i + 15 <= len(data):
                            frames['SPL_56_35_35'].append(data[i:i+15])
                            i += 15
                        else:
                            i += 1
                    elif data[i+4] == 0x95 and data[i+5] == 0x35:
                        # Type G: 5C C7 33 56 95 35 ... (special frame)
                        if i + 15 <= len(data):
                            frames['SPL_56_95_35'].append(data[i:i+15])
                            i += 15
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return frames

def analyze_variant_bytes(frames: Dict[str, List[bytes]]) -> Dict[str, Counter]:
    """Extract variant byte (position 6) from each frame type"""
    variants = {}
    for frame_type, frame_list in frames.items():
        if frame_type.startswith('CMD'):
            # For command frames, variant is at position 6
            variant_counter = Counter()
            for frame in frame_list:
                if len(frame) > 6:
                    variant_counter[frame[6]] += 1
            variants[frame_type] = variant_counter
    return variants

def analyze_trailer_patterns(frames: Dict[str, List[bytes]]) -> Dict[str, List[Tuple]]:
    """Analyze trailer bytes in command frames"""
    trailers = {}
    for frame_type, frame_list in frames.items():
        if frame_type.startswith('CMD') and len(frame_list) > 0:
            trailer_data = []
            for frame in frame_list:
                if len(frame) >= 11:
                    # Command frames: bytes 7-10 are trailer
                    payload = frame[3:7]
                    trailer = frame[7:11]
                    trailer_data.append((payload.hex(), trailer.hex()))
            trailers[frame_type] = trailer_data[:20]  # First 20 examples
    return trailers

def analyze_status_frames(frames: Dict[str, List[bytes]]) -> Dict:
    """Analyze status frame patterns"""
    status_data = defaultdict(list)

    for frame_type, frame_list in frames.items():
        if frame_type.startswith('STS'):
            for frame in frame_list[:50]:  # First 50 examples
                if len(frame) >= 28:
                    # Status frame structure: 5C C7 33 35 5A 35 [variant] [payload 8 bytes] [trailer 4 bytes]
                    variant = frame[6]
                    payload = frame[7:19]  # 12 bytes of payload
                    trailer = frame[19:28]

                    status_data['variants'].append(variant)
                    status_data['payloads'].append(payload.hex())
                    status_data['trailers'].append(trailer.hex())

    return status_data

def find_board_sequence(frames: Dict[str, List[bytes]]) -> List[str]:
    """Try to identify board cycling pattern from command frames"""
    # Collect sequential command frames
    all_cmds = []
    for frame_type in ['CMD_35_96_A5', 'CMD_56_56_A5', 'CMD_56_96_A5']:
        if frame_type in frames:
            for frame in frames[frame_type]:
                all_cmds.append((frame_type, frame))

    # Look for patterns in byte 3 (0x35 vs 0x56 might indicate boards)
    sequence = []
    for frame_type, frame in all_cmds[:30]:
        board_byte = frame[3]
        sequence.append(f"{board_byte:02X}")

    return sequence

def main():
    import sys

    files = [
        '/Users/delta/arduinostuffs/ctinterface/capture_20251111_142403.log',
        '/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.log',
        '/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log'
    ]

    for filename in files:
        print(f"\n{'='*80}")
        print(f"Analyzing: {filename.split('/')[-1]}")
        print(f"{'='*80}\n")

        # Parse frames
        raw_frames = parse_log_file(filename)
        print(f"Total frames captured: {len(raw_frames)}")

        # Concatenate first 100 frames for analysis
        combined = b''.join(raw_frames[:100])

        # Find sync sequences
        syncs = find_sync_sequences(combined)
        sync_types = Counter([f"{s[1]:02X}" for s in syncs])
        print(f"\nSync sequence types (first 100 frames):")
        for sync_type, count in sync_types.most_common():
            print(f"  5C C7 33 {sync_type}: {count} occurrences")

        # Extract frames by type
        frames = extract_frames(combined)
        print(f"\nFrame types identified:")
        for frame_type, frame_list in sorted(frames.items()):
            print(f"  {frame_type}: {len(frame_list)} frames")
            if len(frame_list) > 0:
                print(f"    Example: {frame_list[0].hex(' ').upper()}")

        # Analyze variant bytes
        print(f"\nVariant byte analysis (position 6):")
        variants = analyze_variant_bytes(frames)
        for frame_type, variant_counter in sorted(variants.items()):
            print(f"  {frame_type}:")
            for variant, count in variant_counter.most_common():
                print(f"    0x{variant:02X}: {count} times")

        # Analyze trailer patterns
        print(f"\nTrailer patterns (first 20 examples):")
        trailers = analyze_trailer_patterns(frames)
        for frame_type, trailer_list in sorted(trailers.items()):
            print(f"  {frame_type}:")
            for payload, trailer in trailer_list[:5]:
                print(f"    Payload: {payload.upper()} -> Trailer: {trailer.upper()}")

        # Board sequence
        print(f"\nBoard byte sequence (byte 3):")
        sequence = find_board_sequence(frames)
        print(f"  {' '.join(sequence[:30])}")

        # Status frame analysis
        if 'STS_35_5A_35' in frames:
            print(f"\nStatus frame analysis:")
            status = analyze_status_frames(frames)
            if status:
                print(f"  Variant bytes: {Counter(status['variants']).most_common()}")
                print(f"  Sample payloads (first 5):")
                for payload in status['payloads'][:5]:
                    print(f"    {payload.upper()}")

if __name__ == '__main__':
    main()
