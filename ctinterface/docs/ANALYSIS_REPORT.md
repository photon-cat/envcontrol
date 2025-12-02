# CT2 Protocol Analysis Report
## Systematic Test Capture: capture_20251111_145830.csv

### Executive Summary

This analysis examined a systematic test of the CT2 protocol where channels 1-40 were toggled from OFF to AUTO and back to OFF, followed by setting all channels to AUTO.

### Frame Structure Identified

The CT2 protocol uses a multi-frame structure with the following pattern:

#### Frame Type 1: Status/Addressing Frame
```
5C C7 33 [8 bytes status/addressing data] [optional checksum byte]
```
- Length: 11-12 bytes
- Appears first in each transmission cycle

#### Frame Type 2: Channel Data Frame
```
5C C7 33 35 5A 35 [variant] [8 channel bytes] [4 checksum bytes]
```
- Sync header: `5C C7 33`
- Fixed header: `35 5A 35`
- Variant byte: Typically `65`, sometimes `35` or other values
- **8 channel bytes**: Actual state data for 8 channels
- 4-byte checksum/trailer

**Total frame length**: 16 bytes (3 sync + 4 header + 8 channels + 1 variant included in header = 15, but structure varies)

### Channel Mapping

Based on the 8-byte channel payload blocks:
- **Each frame represents 8 channels**
- For 40 total channels: **5 board frames** × 8 channels = 40 channels

**Board/Channel Mapping** (inferred):
- Board 1: Channels 1-8
- Board 2: Channels 9-16
- Board 3: Channels 17-24
- Board 4: Channels 25-32
- Board 5: Channels 33-40

### Analysis Results: Channels 1-8 (Board 1)

#### Channel 1
- **Unique Values**: 35, 65
- **Total Records**: 495
- **Transitions**: 56 transitions (alternating pattern)
- **State Mapping (HIGH CONFIDENCE)**:
  - **OFF state**: `0x35` (93.9% of captures)
  - **AUTO state**: `0x65` (6.1% of captures)
- **Pattern**: Clean alternating OFF→AUTO→OFF pattern

#### Channel 2
- **Unique Values**: 35 only
- **Total Records**: 495
- **Transitions**: 0 (constant)
- **Status**: No state changes observed
- **Note**: May be unused or stuck in OFF position

#### Channel 3
- **Unique Values**: 35, 99
- **Total Records**: 495
- **Transitions**: 309 transitions (frequent alternating)
- **State Mapping (HIGH CONFIDENCE)**:
  - **OFF state**: `0x35` (68.7% of captures)
  - **AUTO state**: `0x99` (31.3% of captures)
- **Pattern**: Strong alternating pattern, consistent with systematic testing

#### Channel 4
- **Unique Values**: 35, 56, 99 (3 values)
- **Total Records**: 495
- **Transitions**: 347 transitions
- **State Mapping (MEDIUM CONFIDENCE)**:
  - **OFF state**: Likely `0x35`
  - **AUTO state**: `0x99` or `0x56`
  - **Third state**: Possibly AUTO with ON command
- **Pattern**: More complex than channels 1 and 3

#### Channels 5-8
- **Multiple unique values**: 8-9 different byte values each
- **High transition counts**: 118-138 transitions
- **State Mapping**: COMPLEX - requires further analysis
- **Values seen**: 35, 56, 59, 5A, 5C, 65, 6A, 95, AA, C7
- **Note**: These channels show more complex behavior, possibly indicating:
  - AUTO mode with ON commands being sent
  - Multiple state machines or modes
  - Different encoding schemes

### Key Findings

1. **Frame Synchronization**: `5C C7 33` is a reliable sync header
2. **Payload Structure**: Exactly 8 bytes per frame represent 8 channel states
3. **State Encoding**: Each channel's state is represented by a single byte
4. **Common Values**:
   - `0x35` appears to be the most common OFF/idle state
   - `0x99`, `0x65`, `0x56` appear to be AUTO or commanded states
5. **Checksum**: 4-byte trailer follows channel data (format not yet decoded)

### State Value Lookup Table (Preliminary)

| Byte Value | Likely Meaning | Confidence | Channels Observed |
|------------|----------------|------------|-------------------|
| `0x35` | OFF / Idle | HIGH | 1, 2, 3, 4, 5, 6, 7, 8 |
| `0x65` | AUTO (idle) | HIGH | 1 |
| `0x99` | AUTO (idle) | HIGH | 3, 4 |
| `0x56` | AUTO or ON command | MEDIUM | 4, 5, 6, 7, 8 |
| `0x59` | State variant | LOW | 5, 6, 7, 8 |
| `0x5A` | State variant | LOW | 6, 7, 8 |
| `0x5C` | State variant | LOW | 5 |
| `0x6A` | State variant | LOW | 5, 6, 7 |
| `0x95` | State variant | LOW | 5, 6, 7, 8 |
| `0xAA` | State variant | LOW | 5, 6, 7, 8 |
| `0xC7` | State variant | LOW | 6 |
| `0x33` | State variant | LOW | 7 |

### Encoding Pattern Hypothesis

The byte values appear to follow a pattern:
- `0x35` (binary: 0011 0101) - OFF/idle
- `0x65` (binary: 0110 0101) - Differs in bit 4
- `0x99` (binary: 1001 1001) - Differs in bits 3,6,7

Possible bit-field encoding:
- Bits 0-3: Channel-specific ID or state
- Bits 4-7: State flags (OFF, AUTO, ON, etc.)

**Further analysis needed** to decode the complete bit-field structure.

### Recommendations for Protocol Documentation

1. **Add to CT2 Protocol Spec**:
   - Frame structure diagrams showing sync, header, payload, and checksum
   - Channel-to-byte position mapping (8 channels per frame)
   - State value lookup table (expand as more channels analyzed)

2. **Decoder Implementation**:
   - Sync on `5C C7 33` headers
   - Extract 8-byte payload blocks after `35 5A 35 [variant]` pattern
   - Map byte positions 0-7 to channels based on frame sequence

3. **Additional Testing Needed**:
   - Analyze remaining 32 channels (boards 2-5)
   - Test AUTO mode with ON commands to identify command byte values
   - Capture data with rapid state changes to understand timing
   - Test error conditions and malformed frames

4. **Checksum Analysis**:
   - The 4-byte trailer needs reverse engineering
   - May be CRC, simple checksum, or state flags
   - Required for transmitting valid commands

### Data Quality Notes

- **Total frames analyzed**: 495 channel data frames
- **Capture duration**: ~138 seconds (0ms to 138066ms)
- **Frame rate**: Approximately 3.6 frames/second
- **Missing records**: Some record numbers skipped (e.g., 6, 12, 33, 37, 39, 40)
  - May indicate incomplete capture or filtered data
- **Special frames**: Records 13, 31, 52, 71, etc. contain multi-board data
  - These appear periodically (~5 second intervals)
  - Contain status information for multiple boards

### Files Generated

1. `/Users/delta/arduinostuffs/ctinterface/absolutely_final_parser.py` - Python parser script
2. `/Users/delta/arduinostuffs/ctinterface/final_analysis_output.txt` - Complete analysis output
3. `/Users/delta/arduinostuffs/ctinterface/ANALYSIS_REPORT.md` - This report

### Next Steps

1. **Extend parser to extract ALL board data** (not just board 1)
2. **Analyze channels 9-40** using same methodology
3. **Identify patterns in channels with complex behavior** (channels 4-8, likely 12-16, etc.)
4. **Reverse engineer checksum algorithm**
5. **Create complete state transition diagrams** for all 40 channels
6. **Build command encoder** to send valid frames back to the controller
