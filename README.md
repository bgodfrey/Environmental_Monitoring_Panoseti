# Environmental Monitoring for Panoseti

This repository contains the host-side Python code and microcontroller sketches
used to read environmental sensors over USB serial. The current setup supports:

- an Adafruit SHT45/SHT4x Trinkey for temperature and relative humidity
- a DS18B20 temperature probe wired to an Adafruit QT Py RP2040

The Python scripts auto-discover the supported USB devices by VID:PID, open the
serial streams, parse the CSV-style sensor output, and print timestamped readings
on the host computer.

The newer dome telemetry path reads the same sensors locally on each dome/DAQ
node and publishes a latest-value snapshot to the PANOSETI Telemetry gRPC
service, which stores the payload in Redis on the head node.

## Hardware Overview

Add a photo or diagram of the assembled sensor setup here.

Suggested pictures:

- overall sensor mounting / enclosure
- SHT45 Trinkey connection
- DS18B20 wiring to the QT Py RP2040
- host computer USB hub or cabling, if relevant

## Repository Contents

| Path | Purpose |
| --- | --- |
| `readSensors.py` | Main host-side reader. Opens both supported sensors, reads them concurrently, and prints combined temperature/humidity output once per loop. |
| `dome_telemetry.py` | DAQ-node telemetry publisher. Reads both sensors, computes roof/internal temperature delta and dew point, emits an optional telemetry-only heater notice, and publishes the payload through `panoseti_grpc` Telemetry. |
| `dome_a.toml` | Example per-dome DAQ-node config. Sets the dome identity, head-node Telemetry host/port, sensor role mapping, sampling interval, notice threshold, and quiet logging. |
| `dome-temp-telemetry.service` | systemd service template for running `dome_telemetry.py` continuously in the background. |
| `send_dome_telemetry_test.py` | One-shot gRPC smoke test that sends a fake payload without reading hardware sensors. Useful for checking Telemetry server and Redis wiring. |
| `sht45.py` | Python helper for the SHT45/SHT4x Trinkey. Finds the USB serial port, waits for valid streaming data, parses `millis,temp_C,humidity_percent`, and raises clear errors when the firmware reports a problem or the stream times out. |
| `ds18b20.py` | Python helper for the DS18B20-on-RP2040 board. Finds the USB serial port, drains the board startup banner, parses `millis,temp_C`, and surfaces disconnect or timeout errors. |
| `append_temp_stats.py` | Utility for appending summary statistics to a text log containing temperature readings. Reports count, min, max, mean, median, and standard deviation. |
| `read_ds18b20.ino` | Arduino sketch for the QT Py RP2040 + DS18B20 probe. Emits one CSV temperature sample per second over USB serial and prints `ERROR:` lines when the probe is missing or disconnected. |
| `read_sht45/read_sht45.ino` | Arduino sketch for the SHT45/SHT4x Trinkey. Emits one CSV temperature/humidity sample per second over USB serial and prints `ERROR:` lines if initialization or reads fail. |
| `.gitignore` | Ignores Python bytecode cache files. |
| `LICENSE` | GNU General Public License v3. |

## Data Flow

1. Each microcontroller runs its Arduino sketch and streams sensor data over USB
   serial at 115200 baud.
2. The host-side Python wrappers (`sht45.py` and `ds18b20.py`) discover the
   correct serial ports by USB VID:PID.
3. `readSensors.py` opens both devices, reads one sample from each, and prints a
   combined line with the host timestamp.
4. `dome_telemetry.py` can publish the combined snapshot to the Telemetry gRPC
   service. The head-node Telemetry service stores the latest payload in Redis.
5. If a sensor disconnects, stops streaming, or reports an `ERROR:` line, the
   host script closes both serial ports and exits with a non-zero status.

Example combined output:

```text
2026-01-10T16:48:20 | SHT45: 20.71 °C, 42.15 %  DS18B20: 20.62 °C
```

## Python Host Scripts

The host scripts require Python 3 and `pyserial`:

```sh
python3 -m pip install pyserial
```

Run the combined reader from the repository directory:

```sh
python3 readSensors.py
```

At startup, the script prints the detected serial ports:

```text
SHT45 on /dev/ttyACM0, DS18B20 on /dev/ttyACM1
```

The wrappers can also be imported directly if you want to read one sensor from
another script:

```python
from sht45 import SHT45USB
from ds18b20 import DS1820BUSB

sht = SHT45USB()
ds = DS1820BUSB()

try:
    print(sht.read())
    print(ds.read())
finally:
    sht.close()
    ds.close()
```

## Dome Telemetry Publisher

`dome_telemetry.py` is the current prototype for the per-dome environmental
monitor. It runs on the local DAQ node, reads the USB sensors, and pushes a
latest-value payload to the head node's Telemetry gRPC server. The Telemetry
server is responsible for collecting and storing the payload; this script is
responsible for local hardware reads and local dome identity.

For local testing, start the Telemetry server from the `panoseti_grpc` checkout
and make sure Redis is running:

```sh
cd ~/Berkeley/Panoseti/Codebase/panoseti_grpc
PYTHONPATH=src python -m panoseti_grpc.telemetry.server
```

Then run one hardware sample from this repository:

```sh
python dome_telemetry.py --config dome_a.toml --once --verbose
```

The startup output prints the expected Redis key. With the example config, the
key is:

```text
DEV_DOME_ENV_RAL_Laptop
```

Inspect the latest payload in Redis:

```sh
docker exec -it panoseti-redis redis-cli HGETALL DEV_DOME_ENV_RAL_Laptop
```

If Docker requires root on the machine, use `sudo docker ...` or add the user to
the `docker` group and start a new login shell.

### DAQ-node Config

Each deployed dome should have its own TOML config. The local config is separate
from the `panoseti_grpc` server TOML:

- `dome_a.toml` says who this DAQ node is, where to publish, how often to
  sample, which sensor is roof/internal temperature, and whether quiet logging
  is enabled.
- `panoseti_grpc` `telemetry_config.toml` says how the head-node Telemetry
  server maps device types to Redis prefixes and storage behavior.

Important fields in `dome_a.toml`:

```toml
[dome]
device_id = "RAL_Laptop"

[telemetry]
host = "localhost"
port = 50051
device_type = "dome_environment"
interval_seconds = 5

[sensors]
roof_source = "ds18b20"
internal_source = "sht45"

[notices]
delta_notice_threshold_c = 2.5

[logging]
quiet = true
```

When `quiet = true`, normal samples are still published to Redis, but the script
only prints startup lines, publish errors, the first sample, and heater-notice
transitions. This keeps the systemd journal from filling with one line every
sample interval.

The heater notice is intentionally telemetry-only. If the absolute roof/internal
temperature difference is at least `delta_notice_threshold_c`, the payload sets:

```text
heater_notice=TURN_ON_HEATER
heater_notice_active=True
```

It does not switch any heater hardware.

### Background Service

`dome-temp-telemetry.service` is a systemd unit template for running the
publisher continuously. Before installing it on a dome, check these paths:

- `WorkingDirectory`
- the Python executable in `ExecStart`
- the path to `dome_telemetry.py`
- the path to that dome's TOML config

Install and start the service:

```sh
sudo cp dome-temp-telemetry.service /etc/systemd/system/dome-temp-telemetry.service
sudo systemctl daemon-reload
sudo systemctl enable --now dome-temp-telemetry.service
```

Useful checks:

```sh
systemctl status dome-temp-telemetry.service
journalctl -u dome-temp-telemetry.service -f
sudo systemctl restart dome-temp-telemetry.service
```

For long-running systems, journal size should be capped globally with
`SystemMaxUse` in `/etc/systemd/journald.conf` or a drop-in under
`/etc/systemd/journald.conf.d/`.

## Arduino Sketches

### SHT45 Trinkey

Sketch: `read_sht45/read_sht45.ino`

This firmware initializes the Adafruit SHT4x sensor, sets high precision with no
heater, turns the NeoPixel off, and prints one line per second:

```text
millis,temp_C,humidity_percent
```

Required Arduino libraries:

- `Adafruit SHT4x`
- `Adafruit NeoPixel`

### DS18B20 on QT Py RP2040

Sketch: `read_ds18b20.ino`

This firmware reads the first DS18B20 probe on pin `A0`, sets 12-bit resolution,
turns the NeoPixel off, and prints one line per second:

```text
millis,temp_C
```

Required Arduino libraries:

- `OneWire`
- `DallasTemperature`
- `Adafruit NeoPixel`

## Log Summary Utility

`append_temp_stats.py` reads a text log, extracts temperatures from lines such
as:

```text
2026-01-10T16:48:20 | DS18B20: 20.62 °C
```

and appends a summary block to the same file:

```sh
python3 append_temp_stats.py path/to/log.txt
```

Use sample standard deviation instead of population standard deviation with:

```sh
python3 append_temp_stats.py --sample-stddev path/to/log.txt
```

## Error Handling Notes

The Arduino sketches deliberately print `ERROR:` lines instead of becoming
silent when a sensor is missing or disconnected. The Python readers treat those
lines as sensor failures, close the serial ports, and exit cleanly. This makes
failures easier to detect from systemd, cron, shell scripts, or longer-running
data collection jobs.

## License

This project is distributed under the GNU General Public License v3. See
`LICENSE` for the full text.
