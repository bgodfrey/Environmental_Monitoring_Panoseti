import time

import serial
import serial.tools.list_ports


def find_ds18b20_port():
    """
    Discover the serial port for the DS18B20-on-RP2040 (Adafruit QT Py RP2040)
    by USB VID:PID.

    Returns the device path (e.g. "/dev/ttyACM0").
    Raises RuntimeError if zero or more than one matching device is found.
    """
    matches = [
        p.device
        for p in serial.tools.list_ports.comports()
        if p.vid == DS1820BUSB.USB_VID and p.pid == DS1820BUSB.USB_PID
    ]
    if not matches:
        raise RuntimeError(
            f"No DS18B20 found (looking for USB {DS1820BUSB.USB_VID:04x}:"
            f"{DS1820BUSB.USB_PID:04x}). Is it plugged in?"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple DS18B20 devices found ({matches}); pass an explicit port="
        )
    return matches[0]


class DS1820BUSB:
    """
    Read temperature data from an RP2040+DS18B20 over USB serial.

    Expected format: "timestamp, temperature_c[, extra]"

    With no port= argument, auto-discovers the device by USB VID:PID.
    """
    # Adafruit QT Py RP2040 (the RP2040 board the DS18B20 is wired to)
    USB_VID = 0x239a
    USB_PID = 0x80f7

    def __init__(self, port=None, baudrate=115200, timeout=2.0, settle_timeout=8.0):
        if port is None:
            port = find_ds18b20_port()
        self.port = port
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        # The QT Py RP2040 auto-resets when the host opens the CDC port and
        # then prints a setup banner ("DS18B20 Test...", "Found N device(s)",
        # the sensor address) before the steady "<ms>, <tempC>" stream
        # starts. Drain that banner so the first read() returns a real sample.
        self._wait_for_stream(settle_timeout)

    def _wait_for_stream(self, settle_timeout):
        deadline = time.monotonic() + settle_timeout
        last_error = None
        while time.monotonic() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            text = line.decode("utf-8", errors="ignore").strip()
            if text.startswith("ERROR"):
                last_error = text
                continue
            try:
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 2:
                    int(parts[0]); float(parts[1])
                    return
            except (ValueError, IndexError):
                continue
        msg = (
            f"DS18B20 on {self.port} did not start streaming within "
            f"{settle_timeout:.1f}s."
        )
        if last_error:
            msg += f" Firmware reported: {last_error!r}"
        raise TimeoutError(msg)

    def read(self):
        """
        Blocking read of one sample.

        Returns:
            (timestamp, temperature_c, extra)
        """
        while True:
            line = self.ser.readline()
            if not line:
                raise TimeoutError("No data received from DS18B20 (timeout).")

            try:
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue

                # Firmware emits "ERROR: ..." periodically when the sensor
                # is disconnected or otherwise unhealthy. Surface it instead
                # of looping silently.
                if text.startswith("ERROR"):
                    raise RuntimeError(f"DS18B20 firmware: {text}")

                parts = [p.strip() for p in text.split(",")]
                if len(parts) < 2:
                    continue

                ts        = int(parts[0])
                temp_c    = float(parts[1])
                extra     = int(parts[2]) if len(parts) > 2 else None

                return ts, temp_c, extra

            except (ValueError, IndexError):
                continue

    def close(self):
        self.ser.close()
