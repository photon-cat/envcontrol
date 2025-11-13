# Channel State Encoding Reference
## Complete Lookup Table for OFF, AUTO, and HAND Modes

---

## State Encoding Values

### Byte Value Definitions

| State | Hex Value | Decimal | Binary | Description |
|-------|-----------|---------|--------|-------------|
| **OFF** | `0x35` | 53 | `0b00110101` | Channel off, switch in OFF position |
| **AUTO** | `0x65` | 101 | `0b01100101` | Switch in AUTO position, circuit inactive |
| **AUTO_ON** | `0x99` | 153 | `0b10011001` | Switch in AUTO position, circuit energized |
| **HAND_1** | `0x56` | 86 | `0b01010110` | Switch moving to HAND, activation step 1 |
| **HAND_2** | `0x5A` | 90 | `0b01011010` | Switch moving to HAND, activation step 2 |
| **HAND_3** | `0x6A` | 106 | `0b01101010` | Switch moving to HAND, activation step 3 |
| **HAND_ON** | `0xAA` | 170 | `0b10101010` | Switch in HAND position, fully energized |

---

## Bit Pattern Analysis

### Binary Comparison

```
State        Binary      Hex   Pattern Notes
------------------------------------------------------------------
OFF          00110101    0x35  Baseline - bits 0,2,4,5 set
AUTO         01100101    0x65  Bit 6 set vs OFF (+ bit 4 cleared)
AUTO_ON      10011001    0x99  Bit 7 set vs AUTO (bits 5,6 cleared)
HAND_1       01010110    0x56  Bits 1,2,4,6 set
HAND_2       01011010    0x5A  Bits 1,3,4,6 set
HAND_3       01101010    0x6A  Bits 1,3,5,6 set
HAND_ON      10101010    0xAA  Alternating bits 1,3,5,7 set
```

### XOR Differences

**OFF vs other states:**
```
OFF  (0x35) = 0b00110101
AUTO (0x65) = 0b01100101  XOR = 0x50 = 0b01010000  (bits 4,6 differ)
HAND (0xAA) = 0b10101010  XOR = 0x9F = 0b10011111  (bits 0,1,2,3,4,7 differ)
```

**HAND mode progression:**
```
0x35 → 0x56:  XOR = 0x63 = 0b01100011  (bits 0,1,5,6 flip)
0x56 → 0x5A:  XOR = 0x0C = 0b00001100  (bits 2,3 flip)
0x5A → 0x6A:  XOR = 0x30 = 0b00110000  (bits 4,5 flip)
0x6A → 0xAA:  XOR = 0xC0 = 0b11000000  (bits 6,7 flip)
```

---

## State Detection Logic

### Python Implementation

```python
def decode_channel_state(byte_value):
    """
    Decode channel state from byte value.

    Args:
        byte_value: int (0-255) or hex string

    Returns:
        str: State name and description
    """
    if isinstance(byte_value, str):
        byte_value = int(byte_value, 16)

    state_map = {
        0x35: ("OFF", "Channel disabled"),
        0x65: ("AUTO", "Automatic mode, inactive"),
        0x99: ("AUTO_ON", "Automatic mode, active"),
        0x56: ("HAND_ACTIVATING_1", "Manual mode engaging, step 1"),
        0x5A: ("HAND_ACTIVATING_2", "Manual mode engaging, step 2"),
        0x6A: ("HAND_ACTIVATING_3", "Manual mode engaging, step 3"),
        0xAA: ("HAND_ON", "Manual mode, fully active"),
    }

    if byte_value in state_map:
        return state_map[byte_value]
    else:
        return ("UNKNOWN", f"Undefined state: 0x{byte_value:02X}")


def get_channel_mode(byte_value):
    """
    Get the general mode (OFF/AUTO/HAND) ignoring sub-states.

    Returns:
        str: "OFF", "AUTO", or "HAND"
    """
    if isinstance(byte_value, str):
        byte_value = int(byte_value, 16)

    if byte_value == 0x35:
        return "OFF"
    elif byte_value in [0x65, 0x99]:
        return "AUTO"
    elif byte_value in [0x56, 0x5A, 0x6A, 0xAA]:
        return "HAND"
    else:
        return "UNKNOWN"


def is_channel_active(byte_value):
    """
    Check if channel is energized (ON).

    Returns:
        bool: True if channel is energized
    """
    if isinstance(byte_value, str):
        byte_value = int(byte_value, 16)

    # Energized states: AUTO_ON (0x99) or HAND_ON (0xAA)
    # Also consider HAND activating states as "active"
    return byte_value in [0x99, 0xAA, 0x6A]
```

### Arduino/C++ Implementation

```cpp
enum ChannelState {
    STATE_OFF = 0x35,
    STATE_AUTO = 0x65,
    STATE_AUTO_ON = 0x99,
    STATE_HAND_1 = 0x56,
    STATE_HAND_2 = 0x5A,
    STATE_HAND_3 = 0x6A,
    STATE_HAND_ON = 0xAA
};

enum ChannelMode {
    MODE_OFF,
    MODE_AUTO,
    MODE_HAND,
    MODE_UNKNOWN
};

ChannelMode getChannelMode(uint8_t byteValue) {
    switch(byteValue) {
        case STATE_OFF:
            return MODE_OFF;
        case STATE_AUTO:
        case STATE_AUTO_ON:
            return MODE_AUTO;
        case STATE_HAND_1:
        case STATE_HAND_2:
        case STATE_HAND_3:
        case STATE_HAND_ON:
            return MODE_HAND;
        default:
            return MODE_UNKNOWN;
    }
}

bool isChannelActive(uint8_t byteValue) {
    return (byteValue == STATE_AUTO_ON ||
            byteValue == STATE_HAND_ON ||
            byteValue == STATE_HAND_3);
}

const char* getStateName(uint8_t byteValue) {
    switch(byteValue) {
        case STATE_OFF: return "OFF";
        case STATE_AUTO: return "AUTO";
        case STATE_AUTO_ON: return "AUTO_ON";
        case STATE_HAND_1: return "HAND_1";
        case STATE_HAND_2: return "HAND_2";
        case STATE_HAND_3: return "HAND_3";
        case STATE_HAND_ON: return "HAND_ON";
        default: return "UNKNOWN";
    }
}
```

---

## Channel-to-Byte Mapping

### Board 1 (Channels 1-8)

Based on systematic testing, **partial mapping** identified:

| Channel | Byte Position | Notes |
|---------|---------------|-------|
| 1 | B2 (byte 2) | Confirmed via systematic test |
| 2 | B1 (byte 1) | Confirmed via systematic test |
| 3 | B4 (byte 4) | Confirmed via systematic test |
| 4 | B3 (byte 3) | Confirmed via systematic test |
| 5 | TBD | Need more test data |
| 6 | TBD | Need more test data |
| 7 | TBD | Need more test data |
| 8 | TBD | Need more test data |

**Important**: The byte positions are **NOT in sequential order**! This suggests a non-obvious encoding scheme or hardware multiplexing.

### Boards 2-5 (Channels 9-40)

**Status**: Not yet mapped. Requires analysis of Board 2-5 frames from the protocol capture.

Frame headers for each board:
- Board 1: `5C C7 33 35 5A 35`
- Board 2: `5C C7 33 56 [variant] [variant]`
- Board 3: `5C C7 33 35 [variant] [variant]`
- Board 4: `5C C7 33 56 [variant] [variant]`
- Board 5: `5C C7 33 35 [variant] [variant]`

---

## Frame Structure Reference

### Complete Frame Format

```
Byte Position:  0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15
               ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
               │ 5C │ C7 │ 33 │ Bd │ Vr │ Vr │ P0 │ P1 │ P2 │ P3 │ P4 │ P5 │ P6 │ P7 │ T0 │ T1 │
               └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
                └─────────────┘ └──────────┘ └───────────────────────────────────┘ └─────────┘
                   Header        Board ID              8-byte Payload               Trailer
```

- **Header**: Always `5C C7 33`
- **Board ID**: `35` or `56` (alternates between boards)
- **Variant**: 2 bytes, varies by board (e.g., `5A 35` for Board 1)
- **Payload**: 8 bytes containing channel state information
- **Trailer**: 2 bytes, checksum or sequence number

---

## Usage Examples

### Example 1: Decode Single Channel

```python
# Board 1 frame payload: 65 35 AA 35 35 35 35 35
payload = [0x65, 0x35, 0xAA, 0x35, 0x35, 0x35, 0x35, 0x35]

# Channel 1 is at B2 (byte 2)
ch1_state = decode_channel_state(payload[2])
print(f"Channel 1: {ch1_state}")  # Output: ("HAND_ON", "Manual mode, fully active")

# Channel 2 is at B1 (byte 1)
ch2_state = decode_channel_state(payload[1])
print(f"Channel 2: {ch2_state}")  # Output: ("OFF", "Channel disabled")
```

### Example 2: Monitor State Changes

```python
previous_payload = [0x65, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35, 0x35]
current_payload = [0x65, 0x35, 0x56, 0x35, 0x35, 0x35, 0x35, 0x35]

# Detect which channel changed
for i in range(8):
    if previous_payload[i] != current_payload[i]:
        old_state = decode_channel_state(previous_payload[i])
        new_state = decode_channel_state(current_payload[i])
        print(f"Byte {i} changed: {old_state[0]} -> {new_state[0]}")
        # Output: Byte 2 changed: OFF -> HAND_ACTIVATING_1
```

### Example 3: Detect All Active Channels

```python
payload = [0x65, 0xAA, 0xAA, 0x99, 0x35, 0x35, 0x35, 0x35]

# Map byte positions to channel numbers (for Board 1)
byte_to_channel = {1: 2, 2: 1, 3: 4, 4: 3}  # Partial mapping

active_channels = []
for byte_pos, channel in byte_to_channel.items():
    if is_channel_active(payload[byte_pos]):
        active_channels.append(channel)

print(f"Active channels: {active_channels}")
# Output: Active channels: [1, 2, 4]
```

---

## Known Issues and Limitations

1. **Incomplete channel mapping**: Only channels 1-4 of Board 1 are confirmed. Channels 5-40 need additional testing.

2. **Non-sequential byte positions**: The mapping (Ch1→B2, Ch2→B1, Ch3→B4, Ch4→B3) is non-intuitive. The reason for this encoding is unknown.

3. **Transition timing**: HAND mode activation takes 1.5-2.5 seconds through 4 steps. Real-time applications must account for transition states.

4. **Unknown values**: Additional byte values may exist that haven't been observed yet (e.g., error states, fault conditions).

5. **Trailer bytes**: The 2-byte trailer is not fully decoded. May contain checksums, sequence numbers, or status flags.

---

## Testing Recommendations

To complete the state encoding reference:

1. **Full channel test**: Toggle all 40 channels systematically through all three modes (OFF → AUTO → HAND → AUTO → OFF)

2. **Board coverage**: Capture and analyze frames from all 5 boards

3. **Timing analysis**: Measure exact timing of HAND mode activation steps

4. **Reverse transitions**: Document byte values when switching FROM HAND back to AUTO or OFF

5. **Edge cases**: Test multiple channels active simultaneously, rapid switching, error conditions

---

## Revision History

- **2025-11-11**: Initial version based on systematic HAND mode test analysis
  - Documented OFF, AUTO, AUTO_ON states
  - Discovered HAND mode 4-step activation sequence
  - Mapped channels 1-4 of Board 1
  - Created state detection algorithms

---

## References

- Test log: `/Users/delta/arduinostuffs/ctinterface/capture_20251111_150227.log`
- Analysis script: `/Users/delta/arduinostuffs/ctinterface/final_hand_analysis.py`
- Full report: `/Users/delta/arduinostuffs/ctinterface/HAND_MODE_ANALYSIS_REPORT.md`
