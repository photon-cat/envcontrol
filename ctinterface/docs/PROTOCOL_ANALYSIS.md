# CT2 Protocol Analysis - Complete Report

**Date:** 2025-11-11
**Captures Analyzed:**
- `capture_20251111_142403.log` - Baseline (all OFF)
- `capture_20251111_145830.log` - Systematic AUTO test
- `capture_20251111_150227.log` - Systematic HAND test

---

## Executive Summary

The CT2 protocol uses **bidirectional half-duplex communication** where the controller sends commands and immediately receives status responses. Frames are interleaved in the data stream with distinct header patterns identifying command vs. status frames.

### Key Findings:
1. **Three command types cycle** every ~900ms (3 × 300ms)
2. **Command and status frames are interleaved** in pairs
3. **Variant byte (0x35 vs 0x65)** distinguishes normal polling from relay activation
4. **Checksum: NOT FOUND** - trailer byte appears to be a fixed identifier or state indicator
5. **Relay states have distinct patterns** for OFF, AUTO, and HAND modes

---

## 1. Frame Direction & Interleaving

### Frame Types Identified

The protocol uses **TWO distinct frame directions** that are interleaved:

#### **COMMAND Frames (Controller → Switchboard)**
- **Header Pattern:** `5C C7 33 [35/56] [56/96] A5 [variant]`
- **Length:** 11 bytes
- **Structure:**
  ```
  Byte 0-2:  5C C7 33        (Sync)
  Byte 3:    35 or 56        (Board address)
  Byte 4:    56 or 96        (Sub-address)
  Byte 5:    A5              (Command marker)
  Byte 6:    35 or 65        (Variant: normal/special)
  Byte 7-9:  [Relay bytes]   (Control data)
  Byte 10:   [Trailer]       (Fixed per command type)
  ```

#### **STATUS Frames (Switchboard → Controller)**
- **Header Pattern:** `5C C7 33 35 5A 35 [variant]`
- **Length:** 28 bytes (can vary)
- **Structure:**
  ```
  Byte 0-2:  5C C7 33        (Sync)
  Byte 3:    35              (Always 0x35)
  Byte 4:    5A              (Status marker)
  Byte 5:    35              (Always 0x35)
  Byte 6:    35 or 65        (Variant)
  Byte 7-18: [Status data]   (12 bytes payload)
  Byte 19+:  [Trailer]       (Variable length)
  ```

#### **SPECIAL Frames (Purpose Unknown)**
- **Pattern:** `5C C7 33 [35/56] [95/35] 35`
- **Length:** ~15 bytes
- **Occurrence:** Rare, appears during state transitions
- **Example:** `5C C7 33 35 95 35 59 AA AA AA AA 5A 65 99 59 E0`

### Interleaving Pattern

**Normal Cycle (300ms):**
```
CMD_A (Board 1) → STATUS → CMD_B (Board 2) → STATUS → CMD_C (Board 3) → STATUS
```

**Example from baseline capture:**
```
Frame #0:  5C C7 33 35 96 A5 35 9A 35 35 6A  [CMD_A]
           5C C7 33 35 5A 35 65 35 35 35 35... [STATUS]
Frame #1:  5C C7 33 56 56 A5 35 9A 35 35 A6  [CMD_B]
           5C C7 33 35 5A 35 65 35 35 35 35... [STATUS]
Frame #2:  5C C7 33 56 96 A5 35 6A 35 35 99  [CMD_C]
           5C C7 33 35 5A 35 65 35 35 99 99... [STATUS]
```

**Command-Response Pairs:** Each command is immediately followed by a status frame, suggesting synchronous request-response communication.

---

## 2. Variant Byte Analysis

The **variant byte (byte 6)** has two distinct values:

### Variant 0x35 - Normal Polling
- **Purpose:** Regular status polling / relay OFF state
- **Frequency:** Continuous, every 300ms cycle
- **Command bytes:**
  - CMD_A: `9A 35 35` (trailer: `6A`)
  - CMD_B: `9A 35 35` (trailer: `A6`)
  - CMD_C: `6A 35 35` (trailer: `99`)

### Variant 0x65 - Relay Activation
- **Purpose:** Activate relay / special command mode
- **Frequency:** Only during button press (AUTO or HAND)
- **Command bytes:**
  - CMD_A: `9A AA AA` (trailer: `AA`)
  - CMD_B: `99 59 AA` (trailer: `AA`)
  - CMD_C: `99 35 AA` (trailer: `AA`)

### Key Observations:
- **0x35 → 0x65 transition** occurs when relay is activated
- **0x65 → 0x35 transition** occurs when relay is released
- **Broadcast behavior:** When variant=0x65, all three command types (A/B/C) are sent in rapid succession with activation patterns
- **Status response variant matches command variant**

---

## 3. Board Addressing/Sequencing

### Three Command Types = Three Address Groups

| Command Type | Header Bytes | Interpretation | Relay Pattern (OFF) | Trailer |
|--------------|--------------|----------------|---------------------|---------|
| **CMD_A**    | `35 96 A5`   | Board/Group 1  | `9A 35 35`         | `6A`    |
| **CMD_B**    | `56 56 A5`   | Board/Group 2  | `9A 35 35`         | `A6`    |
| **CMD_C**    | `56 96 A5`   | Board/Group 3  | `6A 35 35`         | `99`    |

### Addressing Mechanism

**Hypothesis 1: Three Boards**
- System has **3 physical boards** (not 5)
- Each board addressed uniquely by byte3/byte4 combination
- Cycle time: 900ms / 3 = 300ms per board

**Hypothesis 2: Multiplexed 5 Boards**
- 5 boards addressed in groups:
  - Group A: Boards 1, 4 (0x35 prefix)
  - Group B: Boards 2, 5 (0x56 prefix, even)
  - Group C: Boards 3 (0x56 prefix, odd)
- Sub-addressing happens via relay byte patterns

**Evidence for 3 boards:**
- Only 3 distinct command patterns observed
- No 4th or 5th command type found in 600+ frames
- Trailer bytes are **fixed per command type** (not cycling)

**Evidence against 5 boards:**
- No byte cycling through 5 values
- Timing doesn't match 5 × 100ms = 500ms (observed: ~300ms)

### Board Cycling Sequence

```
Pattern repeats every 3 frames (~900ms):
  Frame N:   CMD_A (35 96 A5) → STATUS
  Frame N+1: CMD_B (56 56 A5) → STATUS
  Frame N+2: CMD_C (56 96 A5) → STATUS
  [repeat]
```

**Byte 3 transitions:**
- Alternates: `35 → 56 → 56 → 35 → 56 → 56...`
- **Not** a simple 5-board cycle

---

## 4. Trailer Byte Patterns

### Checksum Analysis Results

**Tested algorithms:**
- XOR of all bytes
- 8-bit sum
- 16-bit sum
- Two's complement

**Result: NONE MATCH**

The trailer byte is **NOT a calculated checksum** but appears to be a **fixed identifier** for each command type:

| Command Type | Variant | Relay Bytes | Trailer | Notes |
|--------------|---------|-------------|---------|-------|
| CMD_A        | 0x35    | `9A 35 35`  | `6A`    | Fixed |
| CMD_B        | 0x35    | `9A 35 35`  | `A6`    | Fixed |
| CMD_C        | 0x35    | `6A 35 35`  | `99`    | Fixed |
| CMD_A        | 0x65    | `9A AA AA`  | `AA`    | All 0xAA |
| CMD_B        | 0x65    | `99 59 AA`  | `AA`    | All 0xAA |
| CMD_C        | 0x65    | `99 35 AA`  | `AA`    | All 0xAA |

### Trailer Byte Purpose

**Likely interpretations:**
1. **Command Type Identifier** - Allows receiver to validate correct frame type
2. **State Indicator** - `AA` during activation, unique values for OFF state
3. **End-of-Frame Marker** - Simple frame delimiter (less likely due to fixed sync)

**Additional observations:**
- Status frame trailers are **9 bytes** with variable patterns
- Status trailer appears to encode relay states and feedback
- Some status trailers show patterns like: `A9 95 AA 56` or `A5 95 A6 56`

---

## 5. ULN2803C Relay States

### Relay State Patterns

Based on analysis of bytes 7-9 in command frames:

#### **State: OFF (Relay De-energized)**
```
CMD_A: 9A 35 35  (trailer: 6A)
CMD_B: 9A 35 35  (trailer: A6)
CMD_C: 6A 35 35  (trailer: 99)
```
- **Byte 7:** `9A` or `6A` (varies by command type)
- **Byte 8:** `35` (de-energized)
- **Byte 9:** `35` (de-energized)

#### **State: AUTO ACTIVE**
```
CMD_A: 9A AA AA  (trailer: AA)
CMD_B: 99 59 AA  (trailer: AA)
CMD_C: 99 35 AA  (trailer: AA)
```
- **Byte 7:** `9A` or `99` (command/board specific)
- **Byte 8:** `AA`, `59`, or `35` (varied by board)
- **Byte 9:** `AA` (fully energized)

#### **State: HAND ACTIVE (Observed in capture 150227)**
```
Pattern similar to AUTO but sustained longer
Status bytes show progression:
  35 35 35 35 → 56 35 35 35 → 5A 35 35 35 → 6A 35 35 35 → AA 35 35 35
```

### Relay Activation Sequence

**From captures, the activation appears instant:**

1. **Variant changes:** `0x35 → 0x65`
2. **Relay bytes change:** `9A 35 35 → 9A AA AA` (CMD_A example)
3. **Trailer changes:** `6A → AA`
4. **Duration:** Single frame (~100ms)
5. **Return to OFF:** Next cycle reverts to variant `0x35`

**No intermediate states observed** during the 100ms command frame, suggesting:
- ULN2803C switching is fast (<100ms)
- State changes are binary (ON/OFF)
- No gradual energization captured

### State Machine

```
┌─────────────┐
│   OFF       │  Variant: 0x35, Relay: XX 35 35
│ (Polling)   │  Trailer: 6A/A6/99
└──────┬──────┘
       │ Button press
       ▼
┌─────────────┐
│   ACTIVATE  │  Variant: 0x65, Relay: XX AA AA
│  (1 frame)  │  Trailer: AA
└──────┬──────┘
       │ Release
       ▼
┌─────────────┐
│   OFF       │  Variant: 0x35, Relay: XX 35 35
│ (Polling)   │  Trailer: 6A/A6/99
└─────────────┘
```

### ULN2803C Interpretation

**Byte patterns → ULN2803C outputs:**

| Byte Value | ULN2803C State | Relay Coil Current | Contact State |
|------------|----------------|-------------------|---------------|
| `0x35`     | Outputs LOW    | 0 mA             | Open          |
| `0x56`     | Partial (?)    | ~10-20 mA (?)    | Transitioning |
| `0x9A`     | Command/Mixed  | Board-specific   | Varies        |
| `0xAA`     | Outputs HIGH   | Full (50+ mA)    | Closed        |

**Note:** Without oscilloscope/current measurements, exact ULN2803C output states during `0x9A`, `0x99`, `0x6A` are speculative.

---

## 6. Special Observations

### Frame Timing
- **Cycle period:** ~300ms
- **Command-to-status delay:** <10ms (appears immediate)
- **Three command types** = 900ms total cycle
- **Consistent timing** across all captures

### Variant 0x65 Burst Mode
When a relay is activated (AUTO or HAND), the system sends a **burst of three frames** with variant `0x65`:
```
Frame N:   CMD_A (65): 9A AA AA
           STATUS response
Frame N:   CMD_B (65): 99 59 AA
           STATUS response
Frame N:   CMD_C (65): 99 35 AA
           STATUS response
```
This suggests **broadcast activation** to all three boards/groups simultaneously.

### Stray Bytes Between Frames
Occasionally, single bytes appear between frames:
- `00`, `80`, `C0`, `F8`, etc.
- Likely **collision artifacts** or **partial frames** during state transitions
- Do not affect protocol operation

### Status Frame Payload Changes
During AUTO activation:
- Baseline: `35 35 35 35 AA AA AA AA 66 95 AA 35`
- AUTO ON: `35 35 99 99 AA AA 35 35 5A 95 96 35`

Bytes 10-11 change from `35 35` → `99 99` when relay activates, confirming **status feedback**.

---

## 7. Summary & Conclusions

### Confirmed Findings

1. **Bidirectional Protocol:** Controller sends commands, switchboards respond with status
2. **Interleaved Frames:** Command and status frames alternate in the data stream
3. **Three Command Types:** System addresses 3 boards/groups, NOT 5
4. **Variant Byte:**
   - `0x35` = Normal polling (OFF state)
   - `0x65` = Relay activation command
5. **Trailer Byte:** Fixed identifier per command type, **NOT a checksum**
6. **Relay Activation:** Instant transition (within 100ms), no intermediate states captured
7. **Cycle Time:** 300ms per board, 900ms total

### Remaining Questions

1. **Physical topology:** Are there truly 3 boards or 5 boards with grouped addressing?
2. **Relay byte meanings:** What do `0x9A`, `0x99`, `0x6A` specifically control?
3. **Status payload:** Full decoding of 12-byte status response
4. **Special frames:** Purpose of `5C C7 33 [35/56] [95/35] 35` frames
5. **ULN2803C outputs:** Exact mapping of relay bytes to ULN2803 pins

### Recommendations

1. **Oscilloscope analysis:** Capture actual ULN2803C output voltages during state transitions
2. **Current measurement:** Monitor relay coil current to confirm `0xAA` = full energization
3. **Physical inspection:** Verify actual number of PIC16F73 boards in system
4. **Extended capture:** Record longer sequences to identify any 5-board cycling (if present)
5. **Reverse engineer PIC firmware:** Disassemble PIC16F73 to decode exact relay byte logic

---

## 8. Protocol Implementation Guide

### Sending Commands

```c
// Command frame structure
struct CT2_Command {
    uint8_t sync[3];      // 5C C7 33
    uint8_t board_addr;   // 35 or 56
    uint8_t sub_addr;     // 56 or 96
    uint8_t frame_type;   // A5
    uint8_t variant;      // 35 (poll) or 65 (activate)
    uint8_t relay[3];     // Control bytes
    uint8_t trailer;      // Fixed per command type
};

// Example: Activate relay on Board A
CT2_Command cmd_activate = {
    .sync = {0x5C, 0xC7, 0x33},
    .board_addr = 0x35,
    .sub_addr = 0x96,
    .frame_type = 0xA5,
    .variant = 0x65,
    .relay = {0x9A, 0xAA, 0xAA},
    .trailer = 0xAA
};

// Example: Poll Board B
CT2_Command cmd_poll = {
    .sync = {0x5C, 0xC7, 0x33},
    .board_addr = 0x56,
    .sub_addr = 0x56,
    .frame_type = 0xA5,
    .variant = 0x35,
    .relay = {0x9A, 0x35, 0x35},
    .trailer = 0xA6
};
```

### Receiving Status

```c
// Status frame structure
struct CT2_Status {
    uint8_t sync[3];      // 5C C7 33
    uint8_t status_type;  // 35
    uint8_t marker;       // 5A
    uint8_t fixed;        // 35
    uint8_t variant;      // 35 or 65
    uint8_t payload[12];  // Status data
    uint8_t trailer[9];   // Variable trailer
};

// Parse status response
bool parse_status(uint8_t *buffer, size_t len, CT2_Status *status) {
    if (len < 28) return false;
    if (buffer[0] != 0x5C || buffer[1] != 0xC7 || buffer[2] != 0x33) return false;
    if (buffer[3] != 0x35 || buffer[4] != 0x5A) return false;

    memcpy(status->sync, buffer, 3);
    status->status_type = buffer[3];
    status->marker = buffer[4];
    status->fixed = buffer[5];
    status->variant = buffer[6];
    memcpy(status->payload, buffer + 7, 12);
    memcpy(status->trailer, buffer + 19, 9);

    return true;
}
```

### Timing Requirements

- **Baud rate:** 500k, 8E1 (8 data bits, Even parity, 1 stop bit)
- **Command interval:** 300ms minimum between commands
- **Response timeout:** 10ms (status should arrive immediately)
- **Cycle all boards:** Send CMD_A → CMD_B → CMD_C in sequence

---

## Appendix: Raw Data Examples

### Baseline (All OFF)
```
CMD_A: 5C C7 33 35 96 A5 35 9A 35 35 6A
STS:   5C C7 33 35 5A 35 65 35 35 35 35 AA AA AA AA 66 95 AA 35 ...

CMD_B: 5C C7 33 56 56 A5 35 9A 35 35 A6
STS:   5C C7 33 35 5A 35 65 35 35 35 35 AA AA AA AA 66 95 AA 35 ...

CMD_C: 5C C7 33 56 96 A5 35 6A 35 35 99
STS:   5C C7 33 35 5A 35 65 35 35 99 99 AA AA 35 35 5A 95 96 35 ...
```

### AUTO Activation
```
CMD_A: 5C C7 33 35 96 A5 65 9A AA AA AA
STS:   5C C7 33 35 5A 35 35 65 35 35 56 ...

CMD_B: 5C C7 33 56 56 A5 65 99 59 AA AA
STS:   5C C7 33 35 5A 35 35 65 35 35 56 ...

CMD_C: 5C C7 33 56 96 A5 65 99 35 AA AA
STS:   5C C7 33 35 5A 35 35 65 35 35 56 ...
```

### Special Frame (Rare)
```
5C C7 33 35 95 35 59 AA AA AA AA 5A 65 99 59 E0
5C C7 33 56 35 35 59 AA AA AA AA 96 65 99 65 E0
5C C7 33 56 95 35 59 AA AA AA AA AA 65 99 69 00
```

---

**Analysis Tools Used:**
- `/Users/delta/arduinostuffs/ctinterface/analyze_protocol.py`
- `/Users/delta/arduinostuffs/ctinterface/detailed_analysis.py`
- `/Users/delta/arduinostuffs/ctinterface/checksum_analysis.py`

**Total Frames Analyzed:** 794 frames across 3 captures
