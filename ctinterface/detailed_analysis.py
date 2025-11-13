#!/usr/bin/env python3
"""
Detailed CT2 Protocol Analysis - Frame Interleaving and State Transitions
"""

import re
from collections import defaultdict

def parse_log_file_sequential(filename: str):
    """Parse log file maintaining frame order"""
    frames = []
    with open(filename, 'r') as f:
        for line in f:
            match = re.search(r'DATA 500k_8E1\s+((?:[0-9A-F]{2}\s*)+)', line)
            if match:
                hex_str = match.group(1).strip()
                hex_bytes = bytes.fromhex(hex_str.replace(' ', ''))
                frames.append(hex_bytes)
    return frames

def split_interleaved_frames(data: bytes):
    """Split a data stream into individual frames by sync marker"""
    sync_pattern = bytes([0x5C, 0xC7, 0x33])
    frame_starts = []

    i = 0
    while i < len(data) - 2:
        if data[i:i+3] == sync_pattern:
            frame_starts.append(i)
        i += 1

    # Extract frames between sync markers
    frames = []
    for idx in range(len(frame_starts)):
        start = frame_starts[idx]
        end = frame_starts[idx + 1] if idx + 1 < len(frame_starts) else len(data)
        frames.append(data[start:end])

    return frames

def classify_frame(frame: bytes) -> dict:
    """Classify a frame and extract key information"""
    if len(frame) < 7:
        return {'type': 'INCOMPLETE', 'raw': frame.hex()}

    sync = frame[0:3]
    byte3 = frame[3]
    byte4 = frame[4]
    byte5 = frame[5]
    variant = frame[6] if len(frame) > 6 else None

    result = {
        'sync': sync.hex(),
        'byte3': f"{byte3:02X}",
        'byte4': f"{byte4:02X}",
        'byte5': f"{byte5:02X}",
        'variant': f"{variant:02X}" if variant else None,
        'length': len(frame),
        'raw': frame.hex(' ').upper()
    }

    # Classify by header pattern
    if byte3 == 0x35 and byte4 == 0x96 and byte5 == 0xA5:
        result['type'] = 'CMD_A'
        result['direction'] = 'TO_BOARD'
        result['board_id'] = 1  # Tentative
        if len(frame) >= 11:
            result['payload'] = frame[7:11].hex().upper()
            result['trailer_byte'] = f"{frame[10]:02X}"
    elif byte3 == 0x56 and byte4 == 0x56 and byte5 == 0xA5:
        result['type'] = 'CMD_B'
        result['direction'] = 'TO_BOARD'
        result['board_id'] = 2  # Tentative
        if len(frame) >= 11:
            result['payload'] = frame[7:11].hex().upper()
            result['trailer_byte'] = f"{frame[10]:02X}"
    elif byte3 == 0x56 and byte4 == 0x96 and byte5 == 0xA5:
        result['type'] = 'CMD_C'
        result['direction'] = 'TO_BOARD'
        result['board_id'] = 3  # Tentative
        if len(frame) >= 11:
            result['payload'] = frame[7:11].hex().upper()
            result['trailer_byte'] = f"{frame[10]:02X}"
    elif byte3 == 0x35 and byte4 == 0x5A and byte5 == 0x35:
        result['type'] = 'STATUS'
        result['direction'] = 'FROM_BOARD'
        if len(frame) >= 19:
            result['payload'] = frame[7:19].hex().upper()
            result['trailer'] = frame[19:].hex().upper()
    elif byte3 in [0x35, 0x56] and byte4 in [0x95, 0x35] and byte5 == 0x35:
        result['type'] = 'SPECIAL'
        result['direction'] = 'UNKNOWN'
    else:
        result['type'] = 'UNKNOWN'

    return result

def analyze_relay_states(frames, start_idx=0, count=50):
    """Analyze relay state bytes in command frames"""
    print(f"\n{'='*100}")
    print(f"RELAY STATE ANALYSIS (frames {start_idx}-{start_idx+count})")
    print(f"{'='*100}\n")

    for idx, frame_bytes in enumerate(frames[start_idx:start_idx+count]):
        sub_frames = split_interleaved_frames(frame_bytes)

        for sub_frame in sub_frames:
            info = classify_frame(sub_frame)

            if info['type'] in ['CMD_A', 'CMD_B', 'CMD_C']:
                # Extract relay control bytes
                if len(sub_frame) >= 11:
                    relay_byte7 = sub_frame[7]
                    relay_byte8 = sub_frame[8]
                    relay_byte9 = sub_frame[9]

                    print(f"Frame {start_idx+idx:3d} | {info['type']:6s} | "
                          f"Variant:{info['variant']} | "
                          f"Relay: {relay_byte7:02X} {relay_byte8:02X} {relay_byte9:02X} | "
                          f"Trailer:{info['trailer_byte']}")

def analyze_interleaving_pattern(filename: str, num_frames=30):
    """Analyze how command and status frames are interleaved"""
    print(f"\n{'='*100}")
    print(f"FRAME INTERLEAVING PATTERN: {filename.split('/')[-1]}")
    print(f"{'='*100}\n")

    frames = parse_log_file_sequential(filename)

    print(f"{'Idx':>4} | {'Type':^10} | {'Dir':^10} | {'B3':>2} {'B4':>2} {'B5':>2} | {'Var':>3} | {'Length':>3} | Sample Bytes")
    print(f"{'-'*100}")

    for idx, frame_bytes in enumerate(frames[:num_frames]):
        # Split interleaved frames
        sub_frames = split_interleaved_frames(frame_bytes)

        for sub_idx, sub_frame in enumerate(sub_frames):
            info = classify_frame(sub_frame)

            # Show first few frames clearly
            sample = sub_frame[:16].hex(' ').upper()
            if len(sub_frame) > 16:
                sample += "..."

            marker = "├─" if sub_idx < len(sub_frames) - 1 else "└─"
            if len(sub_frames) > 1:
                print(f"{idx:4d} {marker} {info['type']:^10s} | {info.get('direction', 'N/A'):^10s} | "
                      f"{info['byte3']:>2s} {info['byte4']:>2s} {info['byte5']:>2s} | "
                      f"{info['variant'] or 'N/A':>3s} | {info['length']:3d} | {sample}")
            else:
                print(f"{idx:4d} │  {info['type']:^10s} | {info.get('direction', 'N/A'):^10s} | "
                      f"{info['byte3']:>2s} {info['byte4']:>2s} {info['byte5']:>2s} | "
                      f"{info['variant'] or 'N/A':>3s} | {info['length']:3d} | {sample}")

def analyze_board_cycling(filename: str, num_frames=60):
    """Analyze the 5-board cycling pattern"""
    print(f"\n{'='*100}")
    print(f"BOARD CYCLING ANALYSIS: {filename.split('/')[-1]}")
    print(f"{'='*100}\n")

    frames = parse_log_file_sequential(filename)

    cmd_sequence = []

    for idx, frame_bytes in enumerate(frames[:num_frames]):
        sub_frames = split_interleaved_frames(frame_bytes)

        for sub_frame in sub_frames:
            info = classify_frame(sub_frame)
            if info['type'] in ['CMD_A', 'CMD_B', 'CMD_C']:
                cmd_sequence.append({
                    'frame_idx': idx,
                    'type': info['type'],
                    'byte3': info['byte3'],
                    'byte4': info['byte4'],
                    'variant': info['variant']
                })

    # Print command sequence
    print("Command Frame Sequence (first 30):")
    print(f"{'Idx':>4} | {'Type':^7} | {'Byte3':>5} | {'Byte4':>5} | {'Var':>3}")
    print("-" * 50)

    for i, cmd in enumerate(cmd_sequence[:30]):
        print(f"{i:4d} | {cmd['type']:^7s} | {cmd['byte3']:>5s} | {cmd['byte4']:>5s} | {cmd['variant']:>3s}")

    # Look for cycling pattern
    print("\nLooking for 5-board cycle pattern...")
    print("Hypothesis: Byte3 alternates 35/56, and sequence repeats every 3-5 frames")

    # Count transitions
    transitions = []
    for i in range(1, len(cmd_sequence)):
        if cmd_sequence[i]['byte3'] != cmd_sequence[i-1]['byte3']:
            transitions.append(i)

    print(f"\nByte3 transitions occur at indices: {transitions[:10]}")

def analyze_variant_byte_detail(filename: str):
    """Detailed analysis of variant byte (position 6)"""
    print(f"\n{'='*100}")
    print(f"VARIANT BYTE DETAILED ANALYSIS: {filename.split('/')[-1]}")
    print(f"{'='*100}\n")

    frames = parse_log_file_sequential(filename)

    variant_examples = defaultdict(list)

    for idx, frame_bytes in enumerate(frames[:100]):
        sub_frames = split_interleaved_frames(frame_bytes)

        for sub_frame in sub_frames:
            if len(sub_frame) >= 7:
                info = classify_frame(sub_frame)
                variant = info.get('variant')
                frame_type = info.get('type')

                if variant and frame_type in ['CMD_A', 'CMD_B', 'CMD_C', 'STATUS']:
                    key = f"{frame_type}_{variant}"
                    if len(variant_examples[key]) < 3:
                        variant_examples[key].append(sub_frame[:15].hex(' ').upper())

    print("Variant Byte Values by Frame Type:")
    print(f"{'Frame Type':^15s} | {'Variant':^8s} | Example")
    print("-" * 80)

    for key in sorted(variant_examples.keys()):
        frame_type, variant = key.rsplit('_', 1)
        for example in variant_examples[key]:
            print(f"{frame_type:^15s} | {variant:^8s} | {example}")

def main():
    files = [
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_142403.log', 'Baseline (all OFF)'),
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.log', 'AUTO test'),
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log', 'HAND test'),
    ]

    for filename, description in files:
        print(f"\n\n{'#'*100}")
        print(f"# {description}")
        print(f"{'#'*100}")

        analyze_interleaving_pattern(filename, num_frames=15)
        analyze_board_cycling(filename, num_frames=50)
        analyze_variant_byte_detail(filename)

        # Detailed relay state analysis for AUTO and HAND tests
        if 'AUTO' in description or 'HAND' in description:
            frames = parse_log_file_sequential(filename)
            analyze_relay_states(frames, start_idx=0, count=30)

if __name__ == '__main__':
    main()
