CT2 RS-485 Protocol Notes
=========================

> Working document summarising everything observed so far on the Chore-Time CT2 IO bus. The information below is reverse-engineered from scope captures, `busprint` dumps, and the serial logs listed in `capture-notes.md`. Expect inaccuracies until we gather more labelled samples.

System Architecture (CORRECTED)
--------------------------------

```
Host (CT2 master MCU)  <--RS-485 bus-->  Controller backplane  <--ribbon-->  Switch boards #1-3
```

**Physical board configuration:**
- **Board 1**: 16 switches (channels 1-16)
- **Board 2**: 16 switches (channels 17-32)
- **Board 3**: 8 switches (channels 33-40)
- **Total**: 40 channels across 3 physical boards

- **Host** – polls the bus at ~500 kbps (8 data bits, even parity, 1 stop). Issues round-robin status requests.
- **Controller/backplane** – repeats the poll, aggregates replies from three switch boards.
- **Switch boards** – report HOA switch position and commanded relay state. Boards cycle in sequence: board 1, board 2, board 3, repeat.

### Switch Board Hardware (per channel)

Each switch board contains the following components per channel:

- **PIC16F73** microcontroller – receives RS-485 commands from controller, manages 8 channels
- **74HC273** octal D-type flip-flop – latches channel state
- **ULN2803** Darlington transistor array – current driver for relay coils
- **FET** – energized by PIC to toggle relay when HAND mode is activated
- **HOA switch** – physical 3-position switch (Hand/Off/Auto)
- **Relay** – actual switching element controlled by the above logic

**Key insight:** When HAND mode is selected, the PIC must energize the FET to activate the relay. This physical process takes ~1.5-2.5 seconds and is reflected in the protocol's intermediate state values during activation.

Physical layer
--------------

- RS-485 half-duplex, listen mode works fine with a MAX485 and the `busprint` sketch.
- Measured bit period ≈ 2 µs (Siglent SDS1104X-E), matching 500 kbaud.
- Frames are not simple UART packets with checksum; they look like custom blocks bounded by a repeating sync word.

Frame format (COMPLETE)
-----------------------

### Bidirectional Protocol Discovery

The CT2 protocol uses **half-duplex bidirectional communication** with **interleaved command and status frames**. Each controller command is immediately followed by a switchboard status response.

### TWO Frame Types

#### **COMMAND Frames** (Controller → Switchboard)

```
5C C7 33 | [addr1] [addr2] A5 | [variant] | [relay bytes] | [trailer]
^sync^     ^board address^      ^mode^      ^3 bytes^       ^1 byte^
```

**Structure:**
- Bytes 0-2: `5C C7 33` – sync header
- Byte 3: `35` or `56` – board address part 1
- Byte 4: `56` or `96` – board address part 2
- Byte 5: `A5` – command marker (always `0xA5`)
- Byte 6: `35` or `65` – variant (normal polling vs relay activation)
- Bytes 7-9: Relay control bytes (3 bytes)
- Byte 10: Trailer/identifier

**Total length:** 11 bytes

**Three command types cycle every ~900ms:**

| Type | Bytes 3-4 | Relay (OFF) | Trailer | Target | Channels |
|------|-----------|-------------|---------|--------|----------|
| CMD_A | `35 96` | `9A 35 35` | `6A` | Board 1 | 1-16 (16 channels) |
| CMD_B | `56 56` | `9A 35 35` | `A6` | Board 2 | 17-32 (16 channels) |
| CMD_C | `56 96` | `6A 35 35` | `99` | Board 3 | 33-40 (8 channels) |

**Variant byte:**
- `0x35` = Normal polling (relays OFF)
- `0x65` = Relay activation (AUTO or HAND mode engaged)

When variant = `0x65`, relay bytes change to `XX AA AA` and trailer becomes `AA`.

#### **STATUS Frames** (Switchboard → Controller)

```
5C C7 33 | 35 5A 35 | [variant] | [N-byte payload] | [variable trailer]
^sync^     ^status marker^       ^channel states^
```

**Structure:**
- Bytes 0-2: `5C C7 33` – sync header
- Bytes 3-5: `35 5A 35` – status frame marker (always these values)
- Byte 6: `35` or `65` – variant (echoes command variant)
- Bytes 7+: Status payload (**variable length per board**)
  - **Board 1**: 16 bytes (channels 1-16)
  - **Board 2**: 16 bytes (channels 17-32)
  - **Board 3**: 8 bytes (channels 33-40)
- Variable-length trailer (additional status/metadata)

**Total length:**
- Board 1/2 responses: ~27+ bytes (16-byte payload)
- Board 3 responses: ~19+ bytes (8-byte payload)

### Communication Cycle

**Pattern:** CMD_A → STATUS → CMD_B → STATUS → CMD_C → STATUS (repeats every ~900ms)

```
Time    Direction    Frame Type    Bytes 3-4    Purpose
0ms     CTL→SW      CMD_A         35 96        Poll/command board 1
~50ms   SW→CTL      STATUS        35 5A        Board 1 responds
300ms   CTL→SW      CMD_B         56 56        Poll/command board 2
~350ms  SW→CTL      STATUS        35 5A        Board 2 responds
600ms   CTL→SW      CMD_C         56 96        Poll/command board 3
~650ms  SW→CTL      STATUS        35 5A        Board 3 responds
900ms   [cycle repeats]
```

**Key findings:**
- System uses **3 command addresses** (not 5 as initially assumed)
- Each board responds immediately with status frame (~50ms response time)
- 40 channels are distributed across 3 board groups
- Frame rate: ~3.3 cycles/second (300ms per command-response pair)

Example command/status pairs from baseline capture:

```
# Command to board 1 (normal polling, relays OFF)
5C C7 33 | 35 96 A5 | 35 | 9A 35 35 | 6A
         ^CMD_A addr ^variant ^relay bytes ^trailer

# Status response from board 1
5C C7 33 | 35 5A 35 | 65 | 35 35 35 35 35 35 35 35 A9 95 AA 56
         ^status ID  ^var  ^12-byte payload (8 channels + 4 status)

# Command to board 2
5C C7 33 | 56 56 A5 | 35 | 9A 35 35 | A6
         ^CMD_B addr

# Status response from board 2
5C C7 33 | 35 5A 35 | 65 | 35 35 35 35 35 35 35 35 A9 95 AA 56
```

Payload slots (revised)
-----------------------

Within the 8-byte channel payload, each byte maps directly to one channel:

| Slot | Board 1 ch# | Typical OFF | Typical AUTO | Notes |
|------|-------------|-------------|--------------|-------|
| 1    | 1           | `0x35` (94%) | `0x65` (6%) | High confidence |
| 2    | 2           | `0x35` (100%) | - | No transitions observed |
| 3    | 3           | `0x35` (69%) | `0x99` (31%) | High confidence, 309 transitions |
| 4    | 4           | `0x35` | `0x99`, `0x56`, `0x65`, `0xAA` | Multi-state (4 unique values) |
| 5    | 5           | - | - | Not observed in first 100 frames |
| 6    | 6           | `0xAA` | - | Constant in early frames |
| 7    | 7           | `0xAA` | - | Constant in early frames |
| 8    | 8           | `0xAA` | - | Constant in early frames |

**Per-channel state confidence from systematic testing:**

- **Channel 1:** 56 OFF↔AUTO transitions; OFF=`0x35`, AUTO=`0x65` (very clean)
- **Channel 3:** 309 OFF↔AUTO transitions; OFF=`0x35`, AUTO=`0x99` (clean, high activity)
- **Channels 4-8:** Show complex multi-state behavior (3–9 unique values each), indicating:
  - Possible AUTO+ON command states
  - HOA position encoding
  - Feedback/status bits

All boards follow the same 8-byte payload structure. Each board's 8 bytes represent sequential channels (board 1 = ch 1-8, board 2 = ch 9-16, etc.).

Observed encodings (updated)
-----------------------------

From systematic testing in `capture_20251111_145830` (OFF→AUTO→OFF transitions for all 40 channels):

### Base state values (high confidence)

| Hex Value | Binary | State | Observed in Channels | Description |
|-----------|--------|-------|---------------------|-------------|
| `0x35` | 0011 0101 | **OFF** | All channels | Switch in OFF position |
| `0x59` | 0101 1001 | **AUTO (ON)** | 6 | Switch in AUTO, controller commanding ON |
| `0x65` | 0110 0101 | **AUTO (idle)** | 1, 4 | Switch in AUTO, controller commanding OFF |
| `0x99` | 1001 1001 | **AUTO (ON)** | 3, 4 | Switch in AUTO, controller commanding ON |
| `0xAA` | 1010 1010 | **HAND (ON)** | All channels | Switch in HAND position, manually ON |

### HAND mode activation sequence

From `capture_20251111_150227` (systematic HAND test, channels 1-40):

When toggling a channel from OFF to HAND, it progresses through **intermediate values** over ~2 seconds:

```
0x35 (OFF) → 0x56 → 0x5A → 0x6A → 0xAA (HAND fully ON)
```

Each step takes 300-500ms. Total activation time: **1.5-2.5 seconds**.

**Intermediate HAND values:**
- `0x56` = HAND activation step 1
- `0x5A` = HAND activation step 2
- `0x6A` = HAND activation step 3
- `0xAA` = HAND fully engaged

**Detection logic:** To detect HAND mode, check if `byte_value >= 0x56 AND byte_value != 0x65 AND byte_value != 0x99`. Fully ON HAND = `0xAA`.

#### Hardware activation process

The observed ~2 second activation sequence is due to the physical switching process:

**Switch board components (per channel):**
- **PIC16F73** microcontroller – receives RS-485 commands, controls switching logic
- **74HC273** octal D-type flip-flop – latches state
- **ULN2803** Darlington array – current driver for relay coils
- **FET** – energized by PIC to toggle the relay when HAND mode is activated

When the HOA switch is moved to HAND position:
1. PIC detects physical switch change
2. PIC energizes FET to activate relay
3. Protocol byte values transition through intermediate states (`0x56 → 0x5A → 0x6A`) during this process
4. Once relay is fully energized and latched, byte settles to `0xAA`

The intermediate states likely represent:
- FET energization in progress
- Relay coil energizing
- Mechanical relay contacts closing
- Confirmation/feedback that relay is fully latched

### Binary pattern analysis

Comparing the binary representations reveals bit-level encoding:

```
OFF       = 0b00110101  (0x35)
AUTO idle = 0b01100101  (0x65)  — bit 6 set vs OFF
AUTO ON   = 0b10011001  (0x99)  — bits 4,7 set, bits 2,3,6 flipped vs OFF
HAND ON   = 0b10101010  (0xAA)  — alternating pattern, bits 1,3,5,7 set

XOR (OFF vs HAND) = 0b10011111
```

**Pattern observation:** HAND mode produces a distinctive alternating bit pattern (`10101010`) which makes detection reliable even during transitions.

### Channel-to-byte position mapping (critical discovery)

**IMPORTANT:** From `capture_20251111_150227` analysis, channels do **NOT** map sequentially to byte positions!

**Board 1 mapping (confirmed for channels 1-4):**

| Channel # | Byte Position in Payload | Notes |
|-----------|-------------------------|-------|
| 1 | **2** | NOT position 1! |
| 2 | **1** | NOT position 2! |
| 3 | **4** | NOT position 3! |
| 4 | **3** | NOT position 4! |
| 5-8 | TBD | Requires systematic testing |

This non-sequential mapping must be determined empirically for all 40 channels across all 5 boards.

### State value summary table (complete)

| State | Hex | Binary | Description | Detection |
|-------|-----|--------|-------------|-----------|
| OFF | `0x35` | `0011 0101` | Switch in OFF position | `== 0x35` |
| AUTO idle | `0x65` | `0110 0101` | AUTO, no command | `== 0x65` |
| AUTO ON | `0x59` | `0101 1001` | AUTO, commanded ON (ch 6) | `== 0x59` |
| AUTO ON | `0x99` | `1001 1001` | AUTO, commanded ON (ch 3, 4) | `== 0x99` |
| HAND step 1 | `0x56` | `0101 0110` | HAND activating | `== 0x56` |
| HAND step 2 | `0x5A` | `0101 1010` | HAND activating | `== 0x5A` |
| HAND step 3 | `0x6A` | `0110 1010` | HAND activating | `== 0x6A` |
| HAND ON | `0xAA` | `1010 1010` | HAND fully engaged | `== 0xAA` |

**Critical observation:** AUTO+ON encoding is **channel-specific**. Channel 6 uses `0x59` while channels 3 and 4 use `0x99`. This suggests the byte encoding may include channel-specific bits or that the mapping varies by byte position in the payload.

### Controller Command Behavior (from captures 161459 & 161616)

**Key findings about HOA switch priority:**

1. **Switch in OFF position** (`capture_20251111_161459`):
   - Controller sends activation command with variant=`0x65` and relay bytes `AA AA AA`
   - Switchboard STATUS response shows channel remains at `0x35` (OFF)
   - **Relay stays OFF** - physical switch position overrides controller command
   - Demonstrates: **OFF switch blocks all activation attempts**

2. **Switch in AUTO position** (`capture_20251111_161616`):
   - Initially: channel 6 shows `0x35` in STATUS (AUTO but idle)
   - Controller sends activation command with variant=`0x65` and relay bytes `AA AA AA`
   - Switchboard STATUS response transitions to `0x59` (AUTO+ON)
   - **Relay activates** - controller can command when switch is in AUTO
   - Demonstrates: **AUTO switch allows controller activation**

3. **HOA Control Hierarchy:**
   ```
   HAND position → Manual ON (0xAA), controller ignored
   OFF position  → Forced OFF (0x35), controller ignored
   AUTO position → Controller decides (0x65 idle, 0x59/0x99 ON)
   ```

**Quick state detection logic:**

```python
def decode_state(byte_value):
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
```

Interpreting a capture (updated algorithm)
-------------------------------------------

### Decoder algorithm (revised for 19-byte frames)

1. **Sync:** Search for `5C C7 33` in the byte stream.
2. **Extract header:** Read next 4 bytes: `35 5A 35 [variant]`
   - If header doesn't match `35 5A 35`, skip to next sync.
3. **Extract payload:** Read next 8 bytes (channel data for one board).
4. **Extract trailer:** Read next 4 bytes (checksum/status).
5. **Determine board number:** Based on frame sequence or variant byte.
6. **Map channels:** For board `N`:
   - Channel base = `(N-1) * 8`
   - Payload byte `S` (0-7) → channel `base + S + 1`
7. **Decode state:** Compare payload byte to state table:
   - `0x35` → OFF / Idle
   - `0x65` or `0x99` → AUTO (idle)
   - Other values → AUTO+ON, HAND, or status bits

### Example: Decoding board 1 from capture_20251111_145830

```
Raw frame:
5C C7 33 35 5A 35 65 35 35 99 35 AA AA AA AA 66 95 AA 35
^sync^   ^header^  ^8 channel bytes^       ^trailer^

Decoded:
  Slot 1 (ch 1): 0x35 → OFF
  Slot 2 (ch 2): 0x35 → OFF
  Slot 3 (ch 3): 0x99 → AUTO
  Slot 4 (ch 4): 0x35 → OFF
  Slot 5 (ch 5): 0xAA → (status/unknown)
  Slot 6 (ch 6): 0xAA → (status/unknown)
  Slot 7 (ch 7): 0xAA → (status/unknown)
  Slot 8 (ch 8): 0xAA → (status/unknown)
```

Note: Channels 5-8 consistently show `0xAA` in early frames, suggesting they may represent status bits rather than channel states, or use a different encoding scheme.

Open questions (updated)
------------------------

### Resolved

- ✅ **Bidirectional protocol:** TWO frame types - COMMAND (11 bytes, CTL→SW) and STATUS (variable length, SW→CTL)
- ✅ **Frame interleaving:** Command-response pairs cycle every 300ms (CMD → STATUS → repeat)
- ✅ **Board addressing:** 3 physical boards with distinct address bytes (CMD_A: `35 96`, CMD_B: `56 56`, CMD_C: `56 96`)
- ✅ **Physical topology:** Board 1 (16ch), Board 2 (16ch), Board 3 (8ch) = 40 channels total
- ✅ **Variable payload length:** STATUS responses are 16 bytes (boards 1&2) or 8 bytes (board 3)
- ✅ **Variant byte meaning:** `0x35` = normal polling, `0x65` = relay activation mode
- ✅ **Base state encodings:** `0x35` = OFF, `0x65` = AUTO idle, `0x99` = AUTO ON, `0xAA` = HAND ON
- ✅ **HAND mode detection:** Confirmed activation sequence `0x56 → 0x5A → 0x6A → 0xAA` over ~2 seconds
- ✅ **Binary patterns:** Identified bit-level encoding differences between states
- ✅ **ULN2803C relay control:** Relay bytes `0x35` = outputs LOW (OFF), `0xAA` = outputs HIGH (ON)
- ⚠️  **Channel mapping:** NON-sequential! Ch1→byte2, Ch2→byte1, Ch3→byte4, Ch4→byte3 (partial Board 1)

### Still unknown

- **Complete channel-to-byte mapping:** Full 40-channel map (currently only 4 channels confirmed for Board 1)
- **Status payload composition:** What's in the 16-byte payload for boards 1&2? All channel states, or channel states + metadata?
- **Relay control bytes:** Exact meaning of 3-byte relay control in commands (`9A 35 35` vs `6A 35 35`)
- **Trailer byte purpose:** Fixed identifiers (`6A`, `A6`, `99`, `AA`) - state markers or frame validation?
- **Special frames:** Purpose of rare frames with `95 35` pattern (observed in `capture_20251111_161616` lines 17, 26-28):
  - Example: `5C C7 33 35 95 35 59 A6 AA AA AA AA 65 9A 9A C0`
  - Byte 4 is `0x95` instead of `0x96` or `0x56`
  - Byte 5 is `0x35` instead of `0xA5` (command marker)
  - Could indicate error frames, retry attempts, or alternative command types
- **HAND deactivation:** Transition sequences when toggling HAND→OFF or HAND→AUTO
- **Error/alarm states:** Additional byte values for fault conditions

Next steps
----------

### Immediate priorities

1. ✅ **Complete systematic test analysis** – extend byte-value mapping to all 40 channels
2. ✅ **Bit-field analysis** – binary patterns identified and documented
3. ✅ **Capture AUTO+ON states** – confirmed `0x99` = AUTO with ON command
4. ✅ **Capture HAND states** – confirmed `0xAA` = HAND ON, plus activation sequence
5. **Complete channel mapping** – systematically test all 40 channels to build complete byte-position lookup table
6. **Test HAND deactivation** – capture HAND→OFF and HAND→AUTO transitions
7. **Checksum reverse-engineering** – analyze trailer bytes to find checksum/CRC algorithm
8. **Variant byte analysis** – determine if it encodes board number or other metadata

### Longer-term goals

6. Build a real-time decoder that outputs: `Board N, Channel X: [OFF/AUTO/HAND] [commanded OFF/ON] [relay OFF/ON]`
7. Implement passive monitoring with state-change detection
8. Document the complete protocol for bidirectional communication (if boards transmit back to host)
9. Create a Python library for parsing CT2 frames and publishing to MQTT/web interface
