import serial

class SHT45USB:
    """
    Read SHT45 data from an Adafruit SHT45 Trinkey Temperature/Humidity probe
    """
    def __init__(self, port="/dev/ttyACM0", baudrate=115200, timeout=2.0):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.ser.reset_input_buffer()

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
