Chore-Time CT2 IO RS-485 bus notes
=================================

Hardware context
----------------
- Bus is the 485 network on a Chore-Time CT2 controller.
- Currently three switch boards are present: board 1 (16 channels), board 2 (16 channels), board 3 (8 channels).
- Each channel exposes a Hand / Off / Auto selector that drives a relay; goal is to determine each relay state programmatically.
- Bus monitor is the SAMD21 + MAX485 "busprint" sketch configured for 500 kbaud and hex dump.

Observed traffic (USB console timestamps shown)
---------------------------------------------
```
13:37:01.743 -> LOGGER_READY
13:37:01.743 -> 56 35
13:37:02.040 -> 56 35
13:37:02.338 -> 35 35
13:37:02.634 -> 56 35
13:37:02.930 -> 56 35
13:37:03.096 -> 35 F8 35 56 FF 35 56 FF 35
13:37:03.227 -> 35 35
13:37:03.527 -> 56 35
13:37:03.824 -> 56 35
13:37:04.119 -> 35 35
13:37:04.416 -> 56 35
13:37:04.518 -> 35 FC 35
13:37:04.518 -> 56 00 35
13:37:04.553 -> 56 00 35
13:37:04.712 -> 56 35
13:37:05.046 -> 35 35
13:37:05.312 -> 56 00 35
13:37:05.623 -> 56 35
13:37:05.920 -> 35 35
13:37:06.217 -> 56 35
13:37:06.512 -> 35 FC 35
13:37:06.512 -> 56
13:37:06.545 -> 56 35 56 FC 35
13:37:06.545 -> 56 00 35
13:37:06.805 -> 35 35
13:37:07.132 -> 56 00 35
13:37:07.430 -> 56 35
```

Next steps / ideas
------------------
- Capture a longer window and correlate 0x35/0x56 patterns with known relay toggles.
- Try switching individual channels between Hand/Off/Auto while logging to identify signature frames.
- Consider adding timestamps to each byte or grouping to make state changes easier to spot.

Oscilloscope snapshot (Siglent SDS1104X-E, RS-485 differential probe)
---------------------------------------------------------------------
- Decoder configured for custom 500 kbaud, 8 data bits, parity none, 1 stop (8N1).
- Cursor measurement shows ~2 µs bit periods, matching 500 kHz symbol rate.
- Captured burst repeats 0x56/0x35 pattern seen in UART logs, confirming the monitor is aligned to the physical layer timing.
