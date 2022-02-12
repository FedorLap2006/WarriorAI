import dataclasses
from .mk48 import client, protocol
import asyncio


async def main():
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


asyncio.run(main())
