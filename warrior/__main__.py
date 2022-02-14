import dataclasses
import math
import time
from datetime import timedelta
from .mk48 import client, protocol
import asyncio
from hilbertcurve.hilbertcurve import HilbertCurve


async def init_client():
    my_client = client.Client()
    await my_client.init_player('WarriorAI')
    await my_client.init_session()
    print(my_client.session)
    await asyncio.gather(
        my_client.spawn('fairmileD'),
        my_client.listen_metadata(),
        my_client.listen_session(),
    )

    await my_client.close()


async def main():
    # chunk_size = 64
    # hcurve = HilbertCurve(p=int(math.log2(chunk_size)), n=2, n_procs=0)
    # before = time.time()
    # points = []
    # for v in range(chunk_size**2):
    #     points.append(hcurve.point_from_distance(v))
    # after = time.time()

    # print(timedelta(seconds=after - before).microseconds / 1000)

    await init_client()


asyncio.run(main())
