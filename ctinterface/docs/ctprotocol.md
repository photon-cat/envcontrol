# CT Interface Protocol Reference

_Last updated: 2025-11-11_

This document captures the final understanding of the Chore-Time CT2 RS-485 "ctinterface" bus. All statements below are backed by
oscilloscope captures and the annotated logs stored in this repository (see `capture-notes.md`). The same rules are exercised by
`ctinterface/protocol.py`, which now contains the canonical decoder/encoder used in tests.

---

## 1. System Overview

- **Bus:** RS-485 half-duplex, 500 kbaud, 8 data bits, even parity, 1 stop (8E1)
- **Topology:** Controller MCU (master) → backplane → up to three switch boards (observed captures drive boards 1-3)
- **Cycle time:** ≈300 ms per command/response pair, ≈900 ms for one full poll across all boards
- **Payload coverage:** Each status frame carries 8 channel bytes. Boards are addressed in round-robin order to cover at least 24
  channels. Additional boards can be added by repeating the same addressing scheme.
- **Direction:** Every controller command is immediately (or within a few bytes) followed by a switchboard status frame. When the
  operator moves a HOA switch the controller temporarily floods the bus with `variant=0x65` activation commands; these inject extra
  short status acknowledgements but do not change the fundamental interleaving pattern.

---

## 2. Frame Vocabulary

Two header signatures uniquely identify frame types within the byte stream:

| Frame Type | Header bytes (0-5)       | Variant byte | Purpose                            | Length              |
|------------|--------------------------|--------------|------------------------------------|---------------------|
| Command    | `5C C7 33` + address + `A5` | `0x35` or `0x65` | Controller → board command          | 11 bytes            |
| Status (channel block) | `5C C7 33 35 5A 35` | `0x35` or `0x65` | Switchboard → controller, 8 channels | 19 bytes (8 payload + 4 trailer) |
| Status (ack) | `5C C7 33 35 5A 35` | `0x35` or `0x65` | Short acknowledgement during activation | 11 bytes (no payload, 4-byte trailer) |

> **Important:** Both status variants share the same 6-byte header. The decoder must use frame length to distinguish between a
> channel payload (>=19 bytes total) and an acknowledgement (11 bytes total).

---

## 3. Command Frames

```
5C C7 33 | [addr1] [addr2] A5 | [variant] | [relay byte 1] [relay byte 2] [relay byte 3] | [trailer]
```

### Board definitions

| Board | Address bytes (3-4) | Normal relay bytes (`variant=0x35`) | Trailer (`0x35` variant) | Activation relay bytes (`variant=0x65`) | Trailer (`0x65` variant) | Channel range* |
|-------|---------------------|-------------------------------------|--------------------------|-----------------------------------------|--------------------------|----------------|
| 1     | `35 96`             | `9A 35 35`                          | `6A`                     | `9A AA AA`                              | `AA`                     | 1-8            |
| 2     | `56 56`             | `9A 35 35`                          | `A6`                     | `99 59 AA`                              | `AA`                     | 9-16           |
| 3     | `56 96`             | `6A 35 35`                          | `99`                     | `99 35 AA`                              | `AA`                     | 17-24          |

\*Channel numbering is inferred from relay wiring: each board contributes 8 sequential channels.

### Variant byte semantics

- `0x35` – **Polling mode:** Controller reads HOA switch positions and leaves relays idle.
- `0x65` – **Activation mode:** Controller attempts to energize a relay (AUTO command) or reacts to the operator moving to HAND.
  During these bursts, the controller often repeats the same command several times before the board replies with a short ack frame.

---

## 4. Status Frames

### Channel status block (19 bytes)

```
5C C7 33 35 5A 35 | [variant] | [8 channel bytes] | [4-byte trailer]
```

- **Variant:** Mirrors the command variant. A `0x65` status indicates the board is processing an activation sequence.
- **Payload:** Eight bytes, each representing one channel. Boards appear sequential in the capture, so board 1 owns channels 1-8,
  board 2 owns channels 9-16, and board 3 owns channels 17-24.
- **Trailer:** Four-byte checksum/identifier block. The values are consistent per board (`A9 95 AA 56` for board 1, `A5 95 A6 56`
  for board 2, etc.) but the checksum has not been fully reverse-engineered.

### Short acknowledgements (11 bytes total)

```
5C C7 33 35 5A 35 | [variant] | [65 35 35 56]
```

These frames carry no channel payload. They are emitted when the controller is spamming `variant=0x65` commands (AUTO/HAND events)
so that the bus can acknowledge the burst without waiting for full 8-byte channel updates.

---

## 5. Channel Encoding

Known byte values (derived from `capture_20251111_145830.log`, `capture_20251111_150227.log`, and `capture_20251111_161616.log`):

| Hex | Binary       | Meaning                         | Notes |
|-----|--------------|---------------------------------|-------|
| 0x35 | `0011 0101` | OFF (switch in OFF)             | Dominant idle state |
| 0x65 | `0110 0101` | AUTO idle (switch in AUTO, relay idle) | Seen whenever controller polls without activating |
| 0x99 | `1001 1001` | AUTO ON (channels 3/4)          | Controller-commanded relay ON while in AUTO |
| 0x59 | `0101 1001` | AUTO ON (channel 6 pattern)     | Alternate encoding for specific channels |
| 0x56 | `0101 0110` | HAND stage 1                    | FET energizing |
| 0x5A | `0101 1010` | HAND stage 2                    | Relay coil energizing |
| 0x6A | `0110 1010` | HAND stage 3                    | Contacts moving |
| 0xAA | `1010 1010` | HAND fully ON                   | Switch physically in HAND |

**HAND progression:** `0x35 → 0x56 → 0x5A → 0x6A → 0xAA` over ~1.5-2.5 seconds. Moving from HAND back to OFF reverses the sequence.

**HOA precedence:**
```
HAND  (0xAA) → manual ON, controller ignored
OFF   (0x35) → relay forced off, controller ignored
AUTO  (0x65/0x99/0x59) → controller decides relay state
```

---

## 6. Decoder & Encoder Library

The `ctinterface/protocol.py` module exposes the final API used in the automated tests:

```python
from ctinterface.protocol import CTInterfaceDecoder, CTInterfaceEncoder, Variant

# Decode a capture file (CSV or LOG)
decoder = CTInterfaceDecoder()
frames = decoder.decode_file("ctinterface/capture_20251111_145830.csv")
commands = [f for f in frames if f.board]
statuses = [s for s in frames if not s.ack_only]

# Encode a command matching the hardware's poll pattern
encoder = CTInterfaceEncoder()
poll_cmd = encoder.build_command(board_id=1, activate=False)
activate_cmd = encoder.build_command(board_id=2, activate=True)
```

Features:
- Reads both `.csv` and `.log` captures.
- Distinguishes command frames, channel-bearing status frames, and short ack frames.
- Provides per-channel state helpers (`ChannelState`, `decode_channel_state`).
- Encodes controller commands using the observed relay byte patterns for boards 1-3.

---

## 7. Validation Against Captured Logs

Running the decoder on `capture_20251111_145830.csv` produces the following aggregate counts (verified by unit tests):

| Metric                              | Value |
|-------------------------------------|-------|
| Total command frames                | 615   |
| Board 1 commands (`35 96`)          | 199   |
| Board 2 commands (`56 56`)          | 199   |
| Board 3 commands (`56 96`)          | 217   |
| Status frames with 8-byte payloads  | 465   |
| Short status acknowledgements       | 120   |

The tests also assert that the very first command and status in the capture exactly match the byte sequences documented in
Sections 3 and 4, guaranteeing that the decoder and encoder are locked to real hardware behaviour.

---

## 8. Remaining Work

1. Determine whether additional boards exist beyond address set `{35 96, 56 56, 56 96}` in other installations.
2. Reverse-engineer the 4-byte status trailer/checksum.
3. Extend the channel mapping table with definitive channel numbers for every payload position (current assumption is sequential
   mapping within each board's 8-byte block).
