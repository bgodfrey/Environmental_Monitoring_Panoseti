import time

import serial
import serial.tools.list_ports


def find_sht45_port():
    """
    Discover the serial port for an Adafruit SHT4x Trinkey M0 by USB VID:PID.

    Returns the device path (e.g. "/dev/ttyACM0").
    Raises RuntimeError if zero or more than one matching device is found.
    """
    matches = [
        p.device
        for p in serial.tools.list_ports.comports()
        if p.vid == SHT45USB.USB_VID and p.pid == SHT45USB.USB_PID
    ]
    if not matches:
        raise RuntimeError(
            f"No SHT45 found (looking for USB {SHT45USB.USB_VID:04x}:"
            f"{SHT45USB.USB_PID:04x}). Is it plugged in?"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple SHT45 devices found ({matches}); pass an explicit port="
        )
    return matches[0]


class SHT45USB:
    """
    Read SHT45 data from an Adafruit SHT45 Trinkey Temperature/Humidity probe.

    With no port= argument, auto-discovers the device by USB VID:PID.
    """
    # Adafruit SHT4x Trinkey M0
    USB_VID = 0x239a
    USB_PID = 0x8153

    def __init__(self, port=None, baudrate=115200, timeout=2.0, settle_timeout=8.0):
        if port is None:
            port = find_sht45_port()
        self.port = port
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        # The Trinkey auto-resets when the host opens the CDC port; wait for
        # the firmware to finish setup() and start emitting CSV data before
        # returning, otherwise the first read() races the boot banner.
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
                if len(parts) >= 3:
                    int(parts[0]); float(parts[1]); float(parts[2])
                    return
            except (ValueError, IndexError):
                continue
        msg = (
            f"SHT45 on {self.port} did not start streaming within "
            f"{settle_timeout:.1f}s."
        )
        if last_error:
            msg += f" Firmware reported: {last_error!r}"
        raise TimeoutError(msg)

    def read(self):
        """
        Blocking read of one sample.

        Returns:
            (timestamp, temperature_c, humidity_rh, extra)
        """
        while True:
            line = self.ser.readline()
            if not line:
                raise TimeoutError("No data received from SHT45USB (timeout).")

            try:
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue

                # Firmware emits "ERROR: ..." when sht4.getEvent() fails or
                # the sensor failed to init. Surface it instead of looping
                # silently.
                if text.startswith("ERROR"):
                    raise RuntimeError(f"SHT45 firmware: {text}")

                parts = [p.strip() for p in text.split(",")]
                if len(parts) < 3:
                    continue

                ts        = int(parts[0])
                temp_c    = float(parts[1])
                humidity  = float(parts[2])
                extra     = int(parts[3]) if len(parts) > 3 else None

                return ts, temp_c, humidity, extra

            except (ValueError, IndexError):
                continue

    def close(self):
        self.ser.close()
