# CT2 RS-485 Protocol - Quick Reference

**Last Updated:** 2025-11-11
**Status:** Bidirectional protocol decoded, addressing confirmed, state encodings complete

---

## Protocol Overview

- **Bus Type:** RS-485 half-duplex
- **Baud Rate:** 500 kbaud, 8 data bits, even parity, 1 stop bit (8E1)
- **Communication:** Bidirectional command-response pairs
- **Topology:** Controller ↔ 3 Physical Boards (Board 1: 16ch, Board 2: 16ch, Board 3: 8ch)
- **Total Channels:** 40 channels (16 + 16 + 8)
- **Cycle Time:** ~900ms per complete cycle (3 × 300ms)

---

## Frame Types

### 1. COMMAND Frames (Controller → Switchboard)

**Length:** 11 bytes

```
Offset  Field           Values          Description
------  -----           ------          -----------
0-2     Sync            5C C7 33        Frame synchronization
3-4     Address         35 96           Board group address
                        56 56           (3 unique combinations)
                        56 96
5       Command ID      A5              Always 0xA5
6       Variant         35 or 65        35=polling, 65=activate
7-9     Relay Control   9A 35 35        Relay state bytes (3 bytes)
                        6A 35 35
                        XX AA AA        (AA = relay ON)
10      Trailer         6A, A6, 99, AA  Fixed per command type
```

**Three Command Types:**

| Type   | Address (3-4) | Relay (OFF) | Trailer | Target  | Channels         |
|--------|---------------|-------------|---------|---------|------------------|
| CMD_A  | `35 96`       | `9A 35 35`  | `6A`    | Board 1 | 1-16 (16 ch)     |
| CMD_B  | `56 56`       | `9A 35 35`  | `A6`    | Board 2 | 17-32 (16 ch)    |
| CMD_C  | `56 96`       | `6A 35 35`  | `99`    | Board 3 | 33-40 (8 ch)     |

**Example - CMD_A (normal polling):**
```
5C C7 33 35 96 A5 35 9A 35 35 6A
```

**Example - CMD_A (relay activation):**
```
5C C7 33 35 96 A5 65 9A AA AA AA
```

---

### 2. STATUS Frames (Switchboard → Controller)

**Length:** Variable per board

```
Offset  Field           Values          Description
------  -----           ------          -----------
0-2     Sync            5C C7 33        Frame synchronization
3-5     Status ID       35 5A 35        Always these values (status marker)
6       Variant         35 or 65        Echoes command variant
7+      Payload         [N bytes]       Channel states (N = 16 or 8)
        Trailer         [variable]      Variable length
```

**Payload length per board:**
- **Board 1**: 16 bytes (channels 1-16)
- **Board 2**: 16 bytes (channels 17-32)
- **Board 3**: 8 bytes (channels 33-40)

> **Board 1 slot groups:** The 16 channel bytes are split across two consecutive frames.
> Trailer `59 95 A9 95` carries slots 0-7, trailer `A9 95 A9 5A` carries slots 8-15.

**Example STATUS response (Board 1, 16 channels):**
```
5C C7 33 35 5A 35 65 [16 channel state bytes] [trailer...]
         ^status ID  ^v  ^---- 16-byte payload ----^
```

---

## Communication Cycle

```
Time    | Direction | Frame      | Address  | Target  | Channels    | Payload
--------|-----------|------------|----------|---------|-------------|----------
0ms     | CTL → SW  | CMD_A      | 35 96    | Board 1 | 1-16        | 11 bytes
~50ms   | SW → CTL  | STATUS     | 35 5A    | Board 1 | 1-16        | 16 bytes
300ms   | CTL → SW  | CMD_B      | 56 56    | Board 2 | 17-32       | 11 bytes
~350ms  | SW → CTL  | STATUS     | 35 5A    | Board 2 | 17-32       | 16 bytes
600ms   | CTL → SW  | CMD_C      | 56 96    | Board 3 | 33-40       | 11 bytes
~650ms  | SW → CTL  | STATUS     | 35 5A    | Board 3 | 33-40       | 8 bytes
900ms   | [cycle repeats]
```

**Response time:** ~50ms from command to status

---

## State Encoding

### Channel State Values (in STATUS payload)

| Hex  | Binary       | State          | Description                      |
|------|--------------|----------------|----------------------------------|
| 0x35 | `0011 0101`  | **OFF**        | Switch in OFF position           |
| 0x65 | `0110 0101`  | **AUTO idle**  | AUTO mode, no command            |
| 0x59 | `0101 1001`  | **AUTO ON**    | AUTO mode, commanded ON (ch 6)   |
| 0x99 | `1001 1001`  | **AUTO ON**    | AUTO mode, commanded ON (ch 3,4) |
| 0x56 | `0101 0110`  | **HAND step 1**| HAND activating (FET energizing) |
| 0x5A | `0101 1010`  | **HAND step 2**| HAND activating (coil energized) |
| 0x6A | `0110 1010`  | **HAND step 3**| HAND activating (contacts moving)|
| 0xAA | `1010 1010`  | **HAND ON**    | HAND fully latched               |

> **Slot numbering:** Payload bytes are currently referenced by zero-based slot
> numbers (`slot0…slot7`). The physical channel order is non-sequential and still being
> mapped, so the decoder reports slot positions directly until that mapping is complete.

**Note:** AUTO+ON encoding is channel-specific (0x59 or 0x99 depending on channel).

### HAND Activation Sequence

**Duration:** 1.5-2.5 seconds total

```
OFF (0x35)
    ↓ ~300-500ms
HAND step 1 (0x56) ← FET energizing
    ↓ ~300-500ms
HAND step 2 (0x5A) ← Relay coil energizing
    ↓ ~300-500ms
HAND step 3 (0x6A) ← Contacts moving
    ↓ ~300-500ms
HAND ON (0xAA)     ← Fully latched
```

### Relay Control Bytes (in COMMAND)

**OFF mode (variant = 0x35):**
- CMD_A/B: `9A 35 35`
- CMD_C: `6A 35 35`

**ON mode (variant = 0x65):**
- All commands: `XX AA AA` (where `AA` indicates ULN2803C outputs HIGH)

### HOA Control Hierarchy

**Physical switch position determines controller authority:**

| Switch Position | Controller Authority | STATUS Encoding | Description |
|----------------|---------------------|-----------------|-------------|
| **OFF** | ❌ Blocked | `0x35` | Relay forced OFF, controller commands ignored |
| **AUTO** | ✅ Active | `0x65` (idle) or `0x59`/`0x99` (ON) | Controller can activate/deactivate relay |
| **HAND** | ❌ Blocked | `0xAA` (or `0x56`→`0x5A`→`0x6A` during activation) | Manual ON, controller commands ignored |

**Verified behavior:**
- `capture_20251111_161459`: Controller sends variant=`0x65` (activate) but switch in OFF → relay stays OFF
- `capture_20251111_161616`: Controller sends variant=`0x65` (activate) with switch in AUTO → relay activates, STATUS changes from `0x35` to `0x59`

Even though the controller frames are identical in both captures, the status payloads
diverge because the HOA switch decides whether the command is honored. In `_161459`
every slot stays at `0x35`, telling the controller its ON command was blocked. In
`_161616` the same command causes the relevant slots to flip to `0x59/0x99`
(AUTO+ON), proving that the decoded board state always reflects what the controller
sees on the bus.

---

## Hardware Components

**Per channel on switchboard:**
- **PIC16F73** - Microcontroller (8 channels per PIC)
- **74HC273** - Octal D flip-flop (state latching)
- **ULN2803** - Darlington array (relay drivers)
- **FET** - Controls relay activation in HAND mode
- **Relay** - Actual switching element
- **HOA switch** - Physical 3-position switch (Hand/Off/Auto)

**ULN2803C Control:**
- Input LOW (`0x35`) → Outputs LOW → Relay de-energized
- Input HIGH (`0xAA`) → Outputs HIGH (~5V) → Relay energized

---

## Decoder Implementation

### Python State Detection

```python
def decode_state(byte_value):
    """Decode channel state from status payload byte"""
    if byte_value == 0x35:
        return "OFF"
    elif byte_value == 0x65:
        return "AUTO_IDLE"
    elif byte_value in [0x59, 0x99]:
        return "AUTO_ON"
    elif byte_value in [0x56, 0x5A, 0x6A]:
        return "HAND_ACTIVATING"
    elif byte_value == 0xAA:
        return "HAND_ON"
    else:
        return f"UNKNOWN (0x{byte_value:02X})"

def is_command_frame(data):
    """Check if frame is a command (vs status)"""
    if len(data) < 6:
        return False
    return (data[0:3] == b'\x5C\xC7\x33' and
            data[5] == 0xA5)  # Command marker

def is_status_frame(data):
    """Check if frame is a status response"""
    if len(data) < 6:
        return False
    return (data[0:3] == b'\x5C\xC7\x33' and
            data[3:6] == b'\x35\x5A\x35')  # Status marker
```

### Command Construction

```python
def build_command(board_group, activate=False):
    """Build command frame for board group (1, 2, or 3)"""
    addresses = {
        1: (0x35, 0x96, 0x9A, 0x6A),  # addr1, addr2, relay1, trailer
        2: (0x56, 0x56, 0x9A, 0xA6),
        3: (0x56, 0x96, 0x6A, 0x99)
    }

    addr1, addr2, relay1, trailer = addresses[board_group]
    variant = 0x65 if activate else 0x35

    if activate:
        relay_bytes = [relay1, 0xAA, 0xAA]
        trailer = 0xAA
    else:
        relay_bytes = [relay1, 0x35, 0x35]

    cmd = [0x5C, 0xC7, 0x33, addr1, addr2, 0xA5, variant]
    cmd.extend(relay_bytes)
    cmd.append(trailer)

    return bytes(cmd)
```

---

## Known Channel Mapping (Partial)

**Board Group 1 (CMD_A) - Non-sequential!**

| Channel # | Status Byte Position | Verified |
|-----------|---------------------|----------|
| 1         | 2                   | ✓        |
| 2         | 1                   | ✓        |
| 3         | 4                   | ✓        |
| 4         | 3                   | ✓        |
| 5-8       | TBD                 | -        |

*Note: Complete 40-channel mapping requires systematic testing*

---

## References

- **[ctprotocol.md](ctprotocol.md)** - Complete technical specification
- **[PROTOCOL_ANALYSIS.md](PROTOCOL_ANALYSIS.md)** - Detailed analysis report
- **[capture-notes.md](capture-notes.md)** - Annotated capture log index

---

## Next Steps for Complete Decoding

1. ✅ Bidirectional protocol structure - **COMPLETE**
2. ✅ State encoding table - **COMPLETE**
3. ✅ Board addressing mechanism - **COMPLETE**
4. ✅ Physical topology - **COMPLETE** (Board 1: 16ch, Board 2: 16ch, Board 3: 8ch)
5. ✅ Variable payload lengths - **COMPLETE** (16 bytes or 8 bytes per board)
6. ⚠️ Complete channel-to-byte mapping - **PARTIAL** (4/40 channels confirmed)
7. ❌ Status payload full decode - **IN PROGRESS** (need to verify all 16 bytes are channels, or if some are metadata)

**To complete:**
- Systematic testing of all 40 channels with labeled state transitions to build complete channel-to-byte position mapping
- Verify that Board 1 & 2 STATUS payloads contain exactly 16 channel state bytes (vs 16 channel bytes + metadata)
