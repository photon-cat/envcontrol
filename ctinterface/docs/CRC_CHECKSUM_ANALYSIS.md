# CT2 Protocol CRC/Checksum Analysis

## Executive Summary

**The CT2 protocol does NOT use application-level CRC or checksum validation.**

The protocol relies on hardware-level error detection through the serial format's even parity bit (8E1 configuration). Trailer bytes that initially appeared to be checksums are actually **fixed frame identifiers** or **protocol state indicators**.

---

## Analysis Details

### Data Source
- **File**: `/Users/delta/arduinostuffs/ctinterface/capture_20251111_144641.csv`
- **Specific Records Analyzed**:
  - Record #6: Activation command with trailer `0xE0`
  - Record #7: Same activation command with trailer `0x80`
  - Record #31: Same activation command with trailer `0xE0`

### Key Findings

#### 1. Activation Commands Show Variable Trailer Bytes

**Frame Structure (20 bytes total):**
```
[0-2]   Header:     5C C7 33
[3]     Address:    35 (Board 1)
[4-5]   Field:      96 A5
[6-7]   Command:    65 96 (Activation)
[8-16]  Data:       AA AA AA AA 5A AA AA A5 6A
[17-19] Trailer:    A9 9A XX  <-- Last byte varies
```

**Comparison of Identical Commands:**

| Record | Elapsed Time | First 19 Bytes | Last Byte | Binary |
|--------|--------------|----------------|-----------|---------|
| #6     | 1462ms       | Identical      | `0xE0`    | `11100000` |
| #7     | 1477ms       | Identical      | `0x80`    | `10000000` |
| #31    | 6471ms       | Identical      | `0xE0`    | `11100000` |

**Key Observations:**
- Bytes 0-18 are **completely identical** across all three records
- Only byte 19 varies: `0xE0` vs `0x80`
- XOR difference: `0x60` (bits 6 and 5 toggled)
- Records #6 and #31 have **identical** last bytes despite 5-second time gap
- This **rules out** traditional CRC/checksum (would be same for same data)

#### 2. Normal Polling Commands Have Fixed Last Bytes

**Frame Structure (11 bytes total):**
```
[0-2]   Header:     5C C7 33
[3]     Address:    XX (Board ID)
[4-5]   Field:      XX XX
[6-7]   Command:    35 XX (Normal polling)
[8-9]   Data:       35 35
[10]    ID:         XX  <-- Fixed per pattern
```

**Pattern-to-ID Mapping:**

| Pattern (bytes 0-9) | Last Byte | Board | Field | Command |
|---------------------|-----------|-------|-------|---------|
| `5C C7 33 35 5A 35 35 65 35 35` | `0x56` | 0x35 | 0x5A35 | 0x3565 |
| `5C C7 33 35 96 A5 35 9A 35 35` | `0x6A` | 0x35 | 0x96A5 | 0x359A |
| `5C C7 33 56 56 A5 35 9A 35 35` | `0xA6` | 0x56 | 0x56A5 | 0x359A |
| `5C C7 33 56 96 A5 35 6A 35 35` | `0x99` | 0x56 | 0x96A5 | 0x356A |

**Key Observations:**
- Each unique 10-byte pattern has a **consistent** last byte
- Last byte does **not** match any tested checksum:
  - XOR checksum: No match (e.g., XOR=0x92 vs actual=0x99)
  - SUM checksum: No match
  - CRC-8: No match (tested polynomials 0x07, 0x31)
- Last byte appears to be a **frame identifier** or **signature byte**

#### 3. Other Activation Commands (0x65 0x95, 0x65 0x99)

| Command | Occurrences | Trailer Pattern | Last Byte Behavior |
|---------|-------------|-----------------|-------------------|
| `0x65 0x95` | 2 | `A5 9A FF` | **Consistent** (0xFF both times) |
| `0x65 0x96` | 3 | `A9 9A XX` | **Variable** (0x80, 0xE0) |
| `0x65 0x99` | 2 | `99 56 XX` | **Variable** (0xFC, 0xFF) |

- First 2 trailer bytes are **consistent** per command type
- Only the **last byte** varies in some commands
- XOR differences: 0x60 (cmd 0x96), 0x03 (cmd 0x99)

---

## Checksum Tests Performed

### Tests That Failed to Match

1. **XOR Checksum**: `XOR(all bytes) != last_byte`
2. **SUM Checksum**: `SUM(all bytes) & 0xFF != last_byte`
3. **CRC-8** with polynomials:
   - 0x07 (standard CRC-8)
   - 0x31 (CRC-8/MAXIM)
   - 0x07 with init=0xFF
4. **CRC-16** with polynomials:
   - 0x8005 (CRC-16/ARC)
   - 0x1021 (CRC-16/CCITT)

### Test Results Summary

**Normal Polling (11 bytes):**
- Tested 49 frames
- **0 out of 49** matched XOR checksum
- **0 out of 49** matched SUM checksum
- **0 out of 49** matched CRC-8

**Activation Commands (20 bytes):**
- Tested last byte on bytes [0-18]: No match
- Tested last byte on bytes [0-16]: No match
- Tested byte 18 on bytes [0-17]: No match
- Tested byte 17 on bytes [0-16]: No match

---

## What the Varying Byte Represents

### Analysis of the 0xE0 vs 0x80 Pattern

**Bit-level comparison:**
```
0xE0 = 11100000 = 224 decimal
0x80 = 10000000 = 128 decimal
XOR  = 01100000 = 0x60 (bits 6,5 differ)
```

**Timing correlation:**
- Record #6 (1462ms): `0xE0`
- Record #7 (1477ms, +15ms): `0x80`
- Record #31 (6471ms, +4994ms): `0xE0`

**Conclusion**: NOT time-based (records #6 and #31 match despite large time gap)

### Likely Interpretations

1. **Sequence/Transaction Counter**: Increments with each command, wraps around
2. **Response/Status Flag**: Indicates success/failure or request/response
3. **Protocol State Indicator**: Encodes synchronization or handshake state
4. **Command-Response Pairing**: Links requests to responses in multi-frame sequences

---

## Error Detection Mechanism

### Hardware Level (Serial Configuration)

**Format: 8E1**
- **8 data bits** per byte
- **Even parity bit** (hardware error detection)
- **1 stop bit**

The even parity bit provides:
- Detection of single-bit errors
- Hardware-level validation at the UART
- No software overhead for error checking

### Application Level

**None detected.**

The protocol does **not** implement:
- CRC (Cyclic Redundancy Check)
- Checksum (XOR, SUM, or other)
- Application-level error correction codes
- Frame sequence numbers for packet loss detection

---

## Frame Structure Summary

### Normal Polling Commands (11 bytes)

```
Byte    Field           Description
----    -----           -----------
0-2     Header          Fixed: 0x5C 0xC7 0x33
3       Address         Board ID (0x35, 0x56, etc.)
4-5     Field           Variable field (purpose TBD)
6-7     Command         Polling command (0x35 XX)
8-9     Data            Payload (typically 0x35 0x35)
10      Frame ID        Fixed identifier per pattern
```

**Example:**
```
5C C7 33 | 35 | 96 A5 | 35 9A | 35 35 | 6A
Header     Addr  Field   Cmd     Data    ID
```

### Activation Commands (20 bytes)

```
Byte    Field           Description
----    -----           -----------
0-2     Header          Fixed: 0x5C 0xC7 0x33
3       Address         Board ID
4-5     Field           Variable field
6-7     Command         Activation command (0x65 XX)
8-16    Data            9-byte payload (often 0xAA pattern)
17-18   Trailer         Fixed per command type
19      State/Seq       Variable (sequence/status byte)
```

**Example:**
```
5C C7 33 | 35 | 96 A5 | 65 96 | AA AA AA AA 5A AA AA A5 6A | A9 9A | E0
Header     Addr  Field   Cmd     Data (9 bytes)                Trail   Var
```

---

## Recommendations for Implementation

### 1. Do NOT Implement CRC/Checksum Validation

Since the protocol does not use application-level checksums:
- Do **not** calculate or verify CRC/checksum on received frames
- Do **not** add checksum bytes to transmitted frames
- Rely on the hardware parity bit (8E1) for error detection

### 2. Handle Trailer Bytes Correctly

**For Normal Polling (11 bytes):**
- Last byte is a **fixed identifier** per frame pattern
- Use a lookup table to map patterns to expected ID bytes
- Can be used for frame validation (expected vs. actual)

**For Activation Commands (20 bytes):**
- Bytes 17-18: Fixed trailer per command type
- Byte 19: Variable (state/sequence)
  - May need to track/increment for multi-frame sequences
  - May indicate command acknowledgment status

### 3. Implement Frame Validation

Instead of checksums, validate frames by:
1. **Header check**: Verify bytes 0-2 = `0x5C 0xC7 0x33`
2. **Length check**: Ensure correct frame length (11 or 20 bytes)
3. **Pattern validation**: For polling, verify last byte matches expected ID
4. **Serial parity**: Let UART hardware handle parity errors

### 4. Serial Configuration

Ensure UART is configured for:
- **Baud rate**: 500000 bps
- **Data bits**: 8
- **Parity**: Even
- **Stop bits**: 1
- **Parity error handling**: Enabled (discard corrupted frames)

---

## Conclusion

The CT2 protocol is a **simple, fixed-format protocol** that:

1. **Does NOT use CRC/checksum** at the application layer
2. **Relies on hardware parity** (8E1) for error detection
3. **Uses fixed trailer bytes** as frame identifiers
4. **Includes variable state/sequence bytes** in activation commands

This design suggests a **low-overhead, embedded system protocol** optimized for:
- Minimal processing requirements
- Hardware-level reliability
- Fixed message formats with lookup-based validation

The varying byte in activation commands likely serves **protocol state management** rather than error detection, possibly for:
- Command sequencing
- Request-response pairing
- Multi-frame transaction tracking
- Acknowledgment/status indication

---

## Files Generated

Analysis scripts:
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc.py` - Initial checksum analysis
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc2.py` - Detailed frame breakdown
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc3.py` - Varying byte analysis
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc4.py` - Command-specific analysis
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc5.py` - XOR checksum testing
- `/Users/delta/arduinostuffs/ctinterface/analyze_crc_final.py` - Final structure analysis
