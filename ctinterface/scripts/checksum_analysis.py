#!/usr/bin/env python3
"""
Checksum and Relay State Transition Analysis
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

    frames = []
    for idx in range(len(frame_starts)):
        start = frame_starts[idx]
        end = frame_starts[idx + 1] if idx + 1 < len(frame_starts) else len(data)
        frames.append(data[start:end])

    return frames

def calculate_checksum(data: bytes, method='xor'):
    """Calculate various checksum types"""
    if method == 'xor':
        result = 0
        for byte in data:
            result ^= byte
        return result
    elif method == 'sum8':
        return sum(data) & 0xFF
    elif method == 'sum16':
        return sum(data) & 0xFFFF
    elif method == 'twos_complement':
        return (-sum(data)) & 0xFF
    return None

def analyze_command_checksums(filename: str):
    """Analyze command frame checksums"""
    print(f"\n{'='*100}")
    print(f"CHECKSUM ANALYSIS: {filename.split('/')[-1]}")
    print(f"{'='*100}\n")

    frames = parse_log_file_sequential(filename)
    cmd_frames = []

    for frame_bytes in frames[:100]:
        sub_frames = split_interleaved_frames(frame_bytes)
        for sub_frame in sub_frames:
            if len(sub_frame) >= 11:
                byte3 = sub_frame[3]
                byte4 = sub_frame[4]
                byte5 = sub_frame[5]

                # Check if it's a command frame
                if (byte3 in [0x35, 0x56] and
                    byte4 in [0x56, 0x96] and
                    byte5 == 0xA5):
                    cmd_frames.append(sub_frame[:11])

    print(f"Found {len(cmd_frames)} command frames\n")
    print(f"{'Frame':^10s} | {'Header':^20s} | {'Variant':^8s} | {'Payload':^20s} | {'Trailer':^8s} | XOR | SUM8 | 2sC")
    print("-" * 120)

    for idx, frame in enumerate(cmd_frames[:30]):
        header = frame[3:6]
        variant = frame[6]
        payload = frame[7:10]
        trailer = frame[10]

        # Calculate various checksums on full frame
        xor_full = calculate_checksum(frame[:10], 'xor')
        sum8_full = calculate_checksum(frame[:10], 'sum8')
        twos_comp_full = calculate_checksum(frame[:10], 'twos_complement')

        # Check if trailer matches any checksum
        matches = []
        if trailer == xor_full:
            matches.append("XOR*")
        if trailer == sum8_full:
            matches.append("SUM8*")
        if trailer == twos_comp_full:
            matches.append("2sC*")

        match_str = ','.join(matches) if matches else ''

        print(f"{idx:3d}        | {header.hex(' ').upper():^20s} | {variant:02X}       | "
              f"{payload.hex(' ').upper():^20s} | {trailer:02X}       | "
              f"{xor_full:02X}  | {sum8_full:02X}   | {twos_comp_full:02X}  {match_str}")

def analyze_relay_state_transitions(filename: str, description: str):
    """Analyze relay state transitions in detail"""
    print(f"\n{'='*100}")
    print(f"RELAY STATE TRANSITION ANALYSIS: {description}")
    print(f"{'='*100}\n")

    frames = parse_log_file_sequential(filename)

    # Track state changes per command type
    cmd_states = {
        'CMD_A': [],
        'CMD_B': [],
        'CMD_C': []
    }

    for frame_idx, frame_bytes in enumerate(frames[:200]):
        sub_frames = split_interleaved_frames(frame_bytes)

        for sub_frame in sub_frames:
            if len(sub_frame) >= 11:
                byte3 = sub_frame[3]
                byte4 = sub_frame[4]
                byte5 = sub_frame[5]
                variant = sub_frame[6]

                cmd_type = None
                if byte3 == 0x35 and byte4 == 0x96 and byte5 == 0xA5:
                    cmd_type = 'CMD_A'
                elif byte3 == 0x56 and byte4 == 0x56 and byte5 == 0xA5:
                    cmd_type = 'CMD_B'
                elif byte3 == 0x56 and byte4 == 0x96 and byte5 == 0xA5:
                    cmd_type = 'CMD_C'

                if cmd_type:
                    relay_bytes = sub_frame[7:10]
                    cmd_states[cmd_type].append({
                        'frame': frame_idx,
                        'variant': variant,
                        'relay': relay_bytes.hex().upper(),
                        'byte7': sub_frame[7],
                        'byte8': sub_frame[8],
                        'byte9': sub_frame[9]
                    })

    # Print transitions for each command type
    for cmd_type in ['CMD_A', 'CMD_B', 'CMD_C']:
        states = cmd_states[cmd_type]
        if len(states) == 0:
            continue

        print(f"\n{cmd_type} Relay State Transitions:")
        print(f"{'Frame':>5s} | {'Var':>3s} | {'Byte7':>5s} | {'Byte8':>5s} | {'Byte9':>5s} | {'State':^15s} | Note")
        print("-" * 90)

        prev_state = None
        for state in states[:40]:
            # Classify state
            b7, b8, b9 = state['byte7'], state['byte8'], state['byte9']

            if b7 in [0x35, 0x9A, 0x6A] and b8 == 0x35 and b9 == 0x35:
                state_name = "OFF"
            elif b7 in [0x56, 0x5A, 0x6A] and b8 in [0x35, 0x56, 0x5A, 0x6A] and b9 in [0x35, 0x56, 0x5A, 0x6A]:
                state_name = "TRANSITIONING"
            elif b7 in [0x99, 0x9A] and b8 in [0x59, 0x5A, 0x6A, 0xAA] and b9 == 0xAA:
                state_name = "AUTO_ACTIVE"
            elif b7 == 0xAA and b8 == 0xAA:
                state_name = "HAND_ACTIVE"
            else:
                state_name = "UNKNOWN"

            note = ""
            if prev_state and prev_state != state_name:
                note = f"← {prev_state}"

            print(f"{state['frame']:5d} | {state['variant']:02X}  | {b7:02X}    | {b8:02X}    | {b9:02X}    | "
                  f"{state_name:^15s} | {note}")

            prev_state = state_name

def analyze_board_identification():
    """Determine how boards are identified"""
    print(f"\n{'='*100}")
    print(f"BOARD IDENTIFICATION ANALYSIS")
    print(f"{'='*100}\n")

    print("""
Based on frame pattern analysis:

COMMAND FRAME STRUCTURE:
  Sync: 5C C7 33
  Byte3: Board identifier (35 or 56)
  Byte4: Sub-identifier (56 or 96)
  Byte5: Frame type marker (A5)
  Byte6: Variant (35 = normal, 65 = special/broadcast)
  Bytes7-9: Relay control bytes
  Byte10: Checksum/trailer

BOARD ADDRESSING HYPOTHESIS:
  CMD_A (35 96 A5): Board 1 or Board Set A
  CMD_B (56 56 A5): Board 2 or Board Set B (even)
  CMD_C (56 96 A5): Board 3 or Board Set C (odd)

The system cycles through 3 command types, suggesting either:
  - 3 boards being addressed
  - 1 board with 3 different relay groups
  - Multiplexed addressing across 5 boards in groups

VARIANT BYTE MEANINGS:
  0x35: Normal command (repeating)
  0x65: Special command (broadcast or configuration)

STATUS FRAME STRUCTURE:
  Sync: 5C C7 33
  Byte3: 35 (always)
  Byte4: 5A (status marker)
  Byte5: 35 (always)
  Byte6: Variant (35 or 65)
  Bytes7-18: Status payload (12 bytes)
  Bytes19+: Trailer

The ~300ms cycle time and 3 command types suggest:
  - 100ms per command frame
  - Status response immediately follows each command
  - Total cycle: CMD_A → STS → CMD_B → STS → CMD_C → STS
""")

def main():
    files = [
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_142403.log', 'Baseline (all OFF)'),
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_145830.log', 'AUTO test'),
        ('/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log', 'HAND test'),
    ]

    analyze_board_identification()

    for filename, description in files:
        analyze_command_checksums(filename)

    for filename, description in files:
        if 'AUTO' in description or 'HAND' in description:
            analyze_relay_state_transitions(filename, description)

if __name__ == '__main__':
    main()
