import dataclasses
import math
import time
import random
from datetime import timedelta
from .mk48 import protocol
from .mk48.client import Client
import asyncio
from hilbertcurve.hilbertcurve import HilbertCurve
import logging


async def init_client():
    my_client = Client()
    await my_client.open()
    await my_client.create_player("WarriorAI")
    await my_client.spawn("g5")
    await asyncio.sleep(1)
    # await my_client.send(
    #     protocol.SendChat(
    #         random.choice(
    #             [
    #                 "Hello, this is test!",
    #                 "Beep boop beep",
    #                 "Pog",
    #                 "Woah",
    #                 "Hello everyone!",
    #             ]
    #         )
    #     )
    # )

    await my_client.listen()
    await my_client.close()


async def main():
    logging.basicConfig(format='%(created).6f [%(levelname)-8s]: %(message)s', level=logging.INFO)
    await init_client()

asyncio.run(main())
