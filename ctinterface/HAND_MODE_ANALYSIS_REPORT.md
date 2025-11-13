# HAND Mode Analysis Report
## Test Log: capture_20251111_150227.log

### Test Description
Systematic test toggling channels 1-40 to HAND position (one at a time) and leaving them ON.
This analysis focuses on Board 1 (channels 1-8).

---

## Key Findings

### 1. HAND Mode Encoding Pattern

**HAND mode progression** (observed when toggling a channel from OFF to HAND/ON):
```
0x35 (OFF)  → 0x56 → 0x5A → 0x6A → 0xAA (HAND ON)
```

Binary representation:
```
0x35 = 0b00110101  (OFF - baseline)
0x56 = 0b01010110  (HAND activating - step 1)
0x5A = 0b01011010  (HAND activating - step 2)
0x6A = 0b01101010  (HAND activating - step 3)
0xAA = 0b10101010  (HAND fully ON)
```

### 2. Bit Transition Analysis

XOR differences between consecutive states:
```
0x35 → 0x56: XOR = 0x63 = 0b01100011  (bits 0,1,5,6 flip)
0x56 → 0x5A: XOR = 0x0C = 0b00001100  (bits 2,3 flip)
0x5A → 0x6A: XOR = 0x30 = 0b00110000  (bits 4,5 flip)
0x6A → 0xAA: XOR = 0xC0 = 0b11000000  (bits 6,7 flip)
```

**Key observation**: The transition from OFF (0x35) to HAND (0xAA) goes through 4 intermediate steps, suggesting:
- Either a **gradual activation sequence** (possibly motor ramping)
- Or **bit-by-bit status updates** as the system responds to the switch position change

### 3. Comparison with AUTO Mode

From previous analysis:
- **OFF** = `0x35` = `0b00110101`
- **AUTO** = `0x65` = `0b01100101`
- **HAND** = `0xAA` = `0b10101010`

Bit analysis:
```
OFF  vs AUTO:  XOR = 0x50 = 0b01010000  (bits 4,6 differ)
OFF  vs HAND:  XOR = 0x9F = 0b10011111  (bits 0,1,2,3,4,7 differ)
AUTO vs HAND:  XOR = 0xCF = 0b11001111  (bits 0,1,2,3,6,7 differ)
```

### 4. Channel-to-Byte Mapping (Board 1)

Based on the sequential activation pattern observed:

| Channel | Byte Position | HAND Progression |
|---------|---------------|------------------|
| Ch 1    | B2 (byte 2)   | 35 → 56 → 5A → 6A → AA |
| Ch 2    | B1 (byte 1)   | 35 → 56 → 5A → 6A → AA |
| Ch 3    | B4 (byte 4)   | 35 → 56 → 5A → 6A → AA |
| Ch 4    | B3 (byte 3)   | 35 → 56 → 5A → 6A → AA |
| Ch 5    | (not fully captured) | |
| Ch 6    | (not fully captured) | |
| Ch 7    | (not fully captured) | |
| Ch 8    | (not fully captured) | |

**Note**: The byte position mapping is **NOT sequential**! This suggests the payload is not in channel order but may be:
- Scrambled/multiplexed for some reason
- Following a specific board layout or PCB trace routing
- Using a non-intuitive encoding scheme

### 5. State Encoding Lookup Table

| State | Hex  | Decimal | Binary     | Notes |
|-------|------|---------|------------|-------|
| OFF   | 0x35 | 53      | 0b00110101 | Baseline/inactive |
| AUTO  | 0x65 | 101     | 0b01100101 | Automatic mode |
| AUTO ON | 0x99 | 153   | 0b10011001 | Auto mode, circuit active |
| HAND Step 1 | 0x56 | 86  | 0b01010110 | HAND mode activating |
| HAND Step 2 | 0x5A | 90  | 0b01011010 | HAND mode activating |
| HAND Step 3 | 0x6A | 106 | 0b01101010 | HAND mode activating |
| HAND ON | 0xAA | 170   | 0b10101010 | HAND mode fully active |

### 6. Observed Test Sequence (Board 1)

```
Frame   Elapsed(ms)  Event
--------------------------------------------------
1       0            Baseline: all channels OFF
8       1,805        Ch1 activates (B2=0x56)
17      3,613        Ch1 step 2 (B2=0x5A)
24      5,409        Ch1 step 3 (B2=0x6A)
27      6,312        Ch1 fully ON (B2=0xAA)

30      7,212        Ch2 activates (B1=0x56, B2=0xAA)
33      8,111        Ch2 step 2 (B1=0x5A, B2=0xAA)
36      9,011        Ch2 step 3 (B1=0x6A, B2=0xAA)
39      9,918        Ch2 fully ON (B1=0xAA, B2=0xAA)

43      10,816       Ch3 activates (B4=0x56, B1=AA, B2=AA)
46      11,715       Ch3 step 2 (B4=0x5A)
50      12,623       Ch3 step 3 (B4=0x6A)
53      13,522       Ch3 fully ON (B4=0xAA)

59      14,422       Ch4 activates (B3=0x56)
63      15,323       Ch4 step 2 (B3=0x5A)
67      16,239       Ch4 step 3 (B3=0x6A)
70      17,127       Ch4 fully ON (B3=0xAA)
```

**Timing observation**: Each channel takes approximately **1.5-2.5 seconds** to fully activate through all 4 steps. This suggests either:
- Mechanical switch settling time
- Motor ramp-up time
- Intentional delay in the control system

### 7. Pattern Recognition for HAND Mode Detection

To detect if a channel is in HAND mode:

**Method 1: Exact value match**
```python
if byte_value == 0xAA:
    state = "HAND_ON"
elif byte_value in [0x56, 0x5A, 0x6A]:
    state = "HAND_ACTIVATING"
elif byte_value == 0x35:
    state = "OFF"
elif byte_value in [0x65, 0x99]:
    state = "AUTO" or "AUTO_ON"
```

**Method 2: Bit pattern analysis**
```python
# HAND mode has bit 7, 5, 3, 1 set
# Pattern: 0b10X0X0X0
if (byte_value & 0xAA) == 0xAA:
    state = "HAND_FULL"
elif (byte_value & 0x40) == 0x40:
    state = "HAND_PARTIAL" or "AUTO"
```

**Method 3: Range check**
```python
if byte_value >= 0x56 and byte_value <= 0xAA and byte_value not in [0x65, 0x99]:
    state = "HAND_MODE"
```

---

## Recommendations

1. **For full 40-channel mapping**: Need to analyze all 5 boards to determine byte position for channels 5-40

2. **For real-time detection**: Use the 0xAA value as the definitive "HAND ON" indicator

3. **For transition detection**: Monitor for the 0x56 → 0x5A → 0x6A → 0xAA sequence to detect when a channel is being toggled to HAND mode

4. **For state machine implementation**: Consider the intermediate values (0x56, 0x5A, 0x6A) as "transitioning" states

5. **Further testing needed**:
   - What happens when switching from HAND back to OFF or AUTO?
   - Are the intermediate steps always present or do they depend on timing?
   - Do channels 5-8 follow the same pattern?

---

## Data Quality Notes

- Total Board 1 frames analyzed: **160 frames**
- Unique payload patterns: **27 patterns**
- Test duration: ~42 seconds (0-42,402ms elapsed)
- Frame rate: ~3.8 frames/second (irregular)

The data shows clear, repeatable patterns for the first 4 channels of Board 1. The test appears to have been interrupted or the log truncated before completing channels 5-8 and boards 2-5.

---

## Next Steps

To complete the full 40-channel mapping:
1. Capture or analyze frames for all 5 boards
2. Identify byte positions for channels 5-40
3. Verify the same HAND mode encoding (0x35→0x56→0x5A→0x6A→0xAA) applies to all channels
4. Document any board-specific differences
5. Create a complete lookup table: `channel_map[board][channel] = byte_position`
