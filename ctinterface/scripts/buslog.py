#!/usr/bin/env python3
"""
CT2 RS-485 session logger
Captures raw DATA/NOTE/CONFIG lines from the microcontroller and stores them
with timestamps for later analysis.
"""

import serial
import serial.tools.list_ports
import sys
import time
import struct
import threading
from datetime import datetime
from pathlib import Path


class FrameLogger:
    """Log RS-485 bytes with timestamps and free-form notes"""

    def __init__(self, port=None, baudrate=115200, enable_notes=True):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.log_file = None
        self.csv_file = None
        self.frame_count = 0
        self.start_time = None
        self.enable_notes = enable_notes
        self.note_thread = None
        self._stop_notes = False

    def find_device(self):
        """Auto-detect SAMD21 device"""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            if 'SAMD21' in port.description or 'Arduino' in port.description:
                return port.device
            # Seeeduino XIAO SAMD21
            if port.vid == 0x2886 and port.pid == 0x802F:
                return port.device

        # Fallback: return first available port
        if ports:
            return ports[0].device

        return None

    def connect(self):
        """Connect to device"""
        if not self.port:
            self.port = self.find_device()
            if not self.port:
                print("ERROR: No serial device found")
                return False

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset

            # Wait for LOGGER_READY signal
            timeout = time.time() + 5
            while time.time() < timeout:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line == 'LOGGER_READY':
                        print(f"✓ Connected to {self.port}")
                        return True

            print(f"✓ Connected to {self.port} (no ready signal)")
            return True

        except serial.SerialException as e:
            print(f"ERROR: Cannot open {self.port}: {e}")
            return False

    def open_log_files(self, base_name=None):
        """Open log files for writing"""
        if not base_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"capture_{timestamp}"

        log_path = Path(base_name + ".log")
        csv_path = Path(base_name + ".csv")

        self.log_file = open(log_path, 'w')
        self.csv_file = open(csv_path, 'w')

        # Write CSV header
        self.csv_file.write("record_num,timestamp_ms,elapsed_ms,config,hex_bytes\n")
        self.csv_file.flush()

        print(f"✓ Logging to: {log_path}")
        print(f"✓ CSV output: {csv_path}")

        return True

    def log_data_line(self, timestamp_ms, config_name, hex_bytes):
        """Persist a DATA line"""
        self.frame_count += 1

        if self.start_time is None:
            self.start_time = timestamp_ms

        elapsed = timestamp_ms - self.start_time
        log_line = (
            f"[{timestamp_ms:010d}ms +{elapsed:06d}ms] "
            f"#{self.frame_count:05d} DATA {config_name} {hex_bytes}\n"
        )
        self.log_file.write(log_line)
        csv_line = f"{self.frame_count},{timestamp_ms},{elapsed},{config_name},{hex_bytes}\n"
        self.csv_file.write(csv_line)

        if self.frame_count % 100 == 0:
            self.log_file.flush()
            self.csv_file.flush()

    def log_note(self, timestamp_ms, text):
        """Record a NOTE line"""
        log_line = f"[{timestamp_ms:010d}ms] NOTE {text}\n"
        self.log_file.write(log_line)
        self.log_file.flush()
        print(f"NOTE: {text}")

    def log_status(self, prefix, content):
        self.log_file.write(f"[{prefix}] {content}\n")

    def start_note_thread(self):
        if not self.enable_notes:
            return

        def worker():
            print("Type 'note <text>' (or any text) to tag the log. Ctrl+D to stop notes.")
            while not self._stop_notes:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                if line.lower().startswith("note "):
                    note_text = line[5:].strip()
                else:
                    note_text = line
                try:
                    self.ser.write(f"NOTE {note_text}\n".encode("utf-8"))
                except Exception as exc:
                    print(f"! Failed to send note: {exc}")
                    break

        self.note_thread = threading.Thread(target=worker, daemon=True)
        self.note_thread.start()

    def run(self, duration=None):
        """Run logger"""
        if not self.ser or not self.ser.is_open:
            print("ERROR: Not connected")
            return False

        print("\n" + "="*60)
        print("FRAME LOGGER RUNNING")
        print("="*60)
        print("Power up your drone now to capture from startup")
        print("Press Ctrl+C to stop logging")
        print("="*60 + "\n")
        self.start_note_thread()

        start = time.time()

        try:
            while True:
                if duration and (time.time() - start > duration):
                    break

                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                    if line.startswith('DATA,'):
                        parts = line.split(',', 3)
                        if len(parts) == 4:
                            try:
                                timestamp_ms = int(parts[2])
                            except ValueError:
                                continue
                            config_name = parts[1]
                            hex_bytes = parts[3]
                            self.log_data_line(timestamp_ms, config_name, hex_bytes)

                    elif line.startswith('NOTE,'):
                        parts = line.split(',', 2)
                        if len(parts) >= 3:
                            try:
                                timestamp_ms = int(parts[1])
                            except ValueError:
                                timestamp_ms = 0
                            self.log_note(timestamp_ms, parts[2])

                    elif line.startswith('CONFIG,'):
                        self.log_status('CONFIG', line)
                        print(line)

                    elif line.startswith('STATUS,'):
                        self.log_status('STATUS', line)
                        print(line)

                    elif line.startswith('ERROR,'):
                        self.log_status('ERROR', line)
                        print(f"! {line}")

                time.sleep(0.001)  # Small delay to prevent CPU spin

        except KeyboardInterrupt:
            print("\n\nStopping logger...")

        # Final flush
        self.log_file.flush()
        self.csv_file.flush()

        print(f"\n✓ Logged {self.frame_count} frames")
        print(f"✓ Duration: {(time.time() - start):.1f}s")

        return True

    def close(self):
        """Close connections and files"""
        self._stop_notes = True

        if self.note_thread and self.note_thread.is_alive():
            try:
                self.note_thread.join(timeout=0.5)
            except RuntimeError:
                pass

        if self.ser and self.ser.is_open:
            self.ser.close()

        if self.log_file:
            self.log_file.close()

        if self.csv_file:
            self.csv_file.close()

        print("✓ Closed")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='CT2 RS-485 Session Logger')
    parser.add_argument('-p', '--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('-o', '--output', help='Output file base name (default: capture_TIMESTAMP)')
    parser.add_argument('-d', '--duration', type=float, help='Duration in seconds (default: unlimited)')
    parser.add_argument('--no-notes', action='store_true', help='Disable interactive note entry')

    args = parser.parse_args()

    logger = FrameLogger(port=args.port, baudrate=args.baud, enable_notes=not args.no_notes)

    try:
        if not logger.connect():
            return 1

        if not logger.open_log_files(args.output):
            return 1

        if not logger.run(duration=args.duration):
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        logger.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
