from datetime import datetime
from ds18b20 import DS1820BUSB
from sht45 import SHT45USB

import asyncio
import sys

import serial


async def async_read_sht45(dev: SHT45USB):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, dev.read)

async def async_read_ds18b20(dev: DS1820BUSB):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, dev.read)


# Anything in this tuple is treated as "the sensor link broke" — we log it,
# close cleanly, and exit non-zero instead of letting a traceback escape.
SENSOR_ERRORS = (
    RuntimeError,            # firmware ERROR line, or no device found at startup
    TimeoutError,            # no data within the read timeout
    serial.SerialException,  # USB device yanked, port disappeared mid-read
    OSError,                 # underlying read() syscall failure (e.g. ENODEV)
)


async def main() -> int:
    sht = None
    ds = None
    exit_code = 0

    # --- Startup ------------------------------------------------------------
    try:
        sht = SHT45USB()
        ds  = DS1820BUSB()
    except SENSOR_ERRORS as e:
        print(f"Startup failed: {e}", file=sys.stderr)
        # If only one of the two opened, close it so we don't leak the handle.
        for dev in (sht, ds):
            if dev is not None:
                try: dev.close()
                except Exception: pass
        return 1

    print(f"SHT45 on {sht.port}, DS18B20 on {ds.port}")

    # --- Read loop ----------------------------------------------------------
    try:
        while True:
            sht_task = asyncio.create_task(async_read_sht45(sht))
            ds_task  = asyncio.create_task(async_read_ds18b20(ds))

            try:
                ts_sht, temp_sht, rh_sht, extra_sht = await sht_task
                ts_ds,  temp_ds,  extra_ds         = await ds_task
            except SENSOR_ERRORS as e:
                print(f"Sensor error, shutting down: {e}", file=sys.stderr)
                exit_code = 1
                # Close ports first so the other (still-blocked) read returns,
                # then drain whichever task is still pending so asyncio doesn't
                # warn about an unretrieved exception.
                for dev in (sht, ds):
                    try: dev.close()
                    except Exception: pass
                for t in (sht_task, ds_task):
                    if not t.done():
                        try: await t
                        except Exception: pass
                break

            now = datetime.now().isoformat(timespec="seconds")
            print(f"{now} | SHT45: {temp_sht:.2f} °C, {rh_sht:.2f} %  "
                  f"DS18B20: {temp_ds:.2f} °C")
            await asyncio.sleep(0.1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        # Python 3.11+: asyncio.run() handles Ctrl-C by cancelling the main
        # task, which surfaces here as CancelledError at the current await
        # (not as KeyboardInterrupt). Catch both so either path is graceful.
        print("\nInterrupted, closing...", file=sys.stderr)
    finally:
        for dev in (sht, ds):
            if dev is not None:
                try: dev.close()
                except Exception: pass

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        # Safety net: after cancelling the main task, asyncio.run() re-raises
        # KeyboardInterrupt at the call site. Also covers Ctrl-C during the
        # synchronous startup work before the event loop is awaiting anything.
        sys.exit(0)
