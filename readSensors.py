from datetime import datetime
from ds18b20 import DS1820BUSB 
from sht45 import SHT45USB

import asyncio
import time 

async def async_read_sht45(dev: SHT45USB):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, dev.read)

async def async_read_ds18b20(dev: DS1820BUSB):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, dev.read)


async def main():
    #sht = SHT45USB(port="/dev/ttyACM1")
    ds  = DS1820BUSB(port="/dev/ttyACM0")

    try:
        while True:
            # kick off both reads concurrently
            #sht_task = asyncio.create_task(async_read_sht45(sht))
            ds_task  = asyncio.create_task(async_read_ds18b20(ds))

            #ts_sht, temp_sht, rh_sht, extra_sht = await sht_task
            ts_ds, temp_ds, extra_ds = await ds_task

            now = datetime.now().isoformat(timespec="seconds")
            #print(f"{now} | SHT45: {temp_sht:.2f} \u00B0C, {rh_sht:.2f} %  "
            #      f"DS18B20: {temp_ds:.2f} \u00B0C")

            print(f"{now} | DS18B20: {temp_ds:.2f} \u00B0C")
            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
    	print('Ending things...')
    	#sht.close()
    	ds.close()
    finally:
        #sht.close()
        ds.close()

if __name__ == "__main__":
    asyncio.run(main())