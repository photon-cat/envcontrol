# CT Interface Protocol Writeup

This note consolidates the capture index in `capture-notes.md` with the protocol documents (`ctprotocol.md`, `PROTOCOL_SUMMARY.md`) and the behavior seen in the systematic captures from 2025-11-11.

## Bus & Topology
- RS-485 half-duplex, 500 kbaud, 8 data bits, even parity, 1 stop (8E1).
- Controller polls the switch boards in a fixed round-robin; a command is immediately followed by a status frame.
- Cycle time is ~300 ms per command/status pair, ~900 ms for the three observed address groups.
- Installed system exposes 40 channels (capture `_145830` exercises channels 1–40). Channel numbering used in the captures: 1–16 = board 1, 17–32 = board 2, 33–40 = board 3 (8 channels).

## Frame Vocabulary

### Command (controller → board)
```
5C C7 33 | [addr1] [addr2] A5 | [variant] | [relay1] [relay2] [relay3] | [trailer]
length: 11 bytes
```

| Board | addr1 addr2 | Poll relays (`variant=35`) | Poll trailer | Activate relays (`variant=65`) | Activate trailer | Notes |
|-------|-------------|----------------------------|--------------|--------------------------------|------------------|-------|
| 1     | `35 96`     | `9A 35 35`                 | `6A`         | `9A AA AA`                     | `AA`             | Channels 1–16 |
| 2     | `56 56`     | `9A 35 35`                 | `A6`         | `99 59 AA`                     | `AA`             | Channels 17–32 |
| 3     | `56 96`     | `6A 35 35`                 | `99`         | `99 35 AA`                     | `AA`             | Channels 33–40 |

`variant` semantics:
- `0x35` – normal polling / idle (controller not commanding ON).
- `0x65` – activation. Sent in bursts when AUTO commands are asserted or when a HAND switch moves; the controller repeats the command until the board replies.

### Status (board → controller)
```
5C C7 33 35 5A 35 | [variant] | [payload] | [trailer4]
lengths: 19 bytes with payload, 11 bytes for short acks
```

- Payload: 8 channel bytes. Boards with 16 channels emit two status frames back-to-back; capture `_145830` shows 597 frames covering all 40 channels with this 8-byte chunking.
- Variant echoes the command (`0x35` idle, `0x65` activation in progress).
- Trailers are board identifiers:
  - Board 1: family `6A/66/65/59 95 AA 35` (seen in `_145830`, `_144514`).
  - Board 2: `A9 95 AA 56`.
  - Board 3: `A5 95 A6 56`.
- Short acknowledgements (no payload) appear during activation bursts with trailer `65 35 35 56`; these are 11-byte frames that confirm the board saw the `0x65` command.

## Channel State Encoding (status payload bytes)

| Hex | Meaning | Evidence |
|-----|---------|----------|
| `0x35` | Switch OFF; relay forced off | Baseline captures `_142403`, `_144346` |
| `0x65` | AUTO idle (switch in AUTO, no ON command) | `_144514` with AUTO but no ON command |
| `0x59` | AUTO + ON (channel-specific ON code) | `_161616` (channel 6 commanded ON) |
| `0x99` | AUTO + ON (alternate ON code) | `_145830`, `_161616` (channels 3/4) |
| `0x56` → `0x5A` → `0x6A` → `0xAA` | HAND progression to full ON | `_150227` (HAND sweep across channels) |
| `0xAA` | HAND latched ON | `_150227`, `_144641` |

HAND sequence timing (from `_150227`): roughly 0.3–0.5 s per step, total ~2 s from OFF to fully ON.

## HOA Precedence
- **HAND (`0xAA` or in-flight 0x56/0x5A/0x6A):** manual ON; controller commands ignored.
- **OFF (`0x35`):** physical OFF wins; controller cannot energize the relay (`_161459` shows ON command ignored).
- **AUTO (`0x65` idle, `0x59/0x99` ON):** controller may energize/de-energize. `_161616` shows transition from `0x35` → `0x59` when the controller commands ON with the switch in AUTO.

## Channel/Slot Ordering
- Payload slot order is **non-sequential**. From `_150227` on Board 1: Ch1→byte2, Ch2→byte1, Ch3→byte4, Ch4→byte3. Mapping for remaining channels still needs systematic confirmation, but every board uses a stable slot order once identified.

## What to Watch For in Captures
- `_145830` (Systematic state test): clean 19-byte status frames, 8-byte payloads, trailers above; good for validating OFF vs AUTO encodings across all 40 channels.
- `_150227` (HAND mode sweep): best source for the HAND progression and the non-sequential slot order.
- `_161459` vs `_161616`: paired proof that AUTO switch position gates whether the controller’s ON command takes effect.

## Remaining Unknowns
- Full channel-to-payload slot map for channels 5–40.
- Whether Board 1’s trailer family encodes which half (slots 0–7 vs 8–15) of its 16 channels is being reported or if another marker distinguishes the halves.
- Exact checksum/meaning of the 4-byte trailers (currently treated as board IDs and slot offsets).
