import serial 

class DS1820BUSB:
    """
    Read temperature data from an RP2040+DS18B20 over USB serial.

    Expected format: "timestamp, temperature_c[, extra]"
    """
    def __init__(self, port="/dev/ttyACM1", baudrate=115200, timeout=2.0):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.ser.reset_input_buffer()

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