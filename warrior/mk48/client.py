import asyncio
import json
import logging
import random
from typing import Awaitable, Callable, Optional, cast, Any
from urllib.parse import urlencode
import math

# TODO: typing stubs
from cv2 import (
  VideoWriter, # type: ignore
  VideoWriter_fourcc,  # type: ignore
  destroyAllWindows, # type: ignore
  imshow,  # type: ignore
  cvtColor, # type: ignore
  COLOR_RGB2BGR, # type: ignore
  waitKey, # type: ignore
)
import websockets
import websockets.client
import numpy as np
import PIL.Image 

from . import endpoints, protocol, draw

class Client:
    """Session is the event dispatcher of game events"""

    session: Optional[protocol.SessionCreated]
    ws: websockets.client.WebSocketClientProtocol

    def __init__(
        self,
        update_callback: Callable[['Client', protocol.Update], Awaitable[Any]] | None = None,
        ws_endpoint: str = endpoints.ENDPOINT_WS,
        protocol_name: str = "Json",
    ):
        self.protocol = protocol_name
        self.ws_endpoint = ws_endpoint
        self.update_callback = update_callback

        self.session = None

        self.cached_chunks: dict[tuple[int, int], protocol.Chunk] = {}

    async def send(self, message: protocol.MessageBase):
        return await self.ws.send(message.encode())

    async def control(
        self, *,
        direction: float | None = None,
        velocity: int | None = None,
        submerge: bool = False
    ):
        control = protocol.Control()
        if direction is not None or velocity is not None:
            control.guidance = protocol.Guidance(
                direction_target=direction, velocity_target=velocity
            )
        control.submerge = submerge
        logging.info(f'control command: {control}')
        await self.send(control)
 
    def encode_map_image(self, update: protocol.Update):
        image = self.hud_image.copy()
        image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
        draw.draw_world_border(image, cast(float, update.world_radius))
        frame = cvtColor(np.array(image), COLOR_RGB2BGR)
        return frame

    async def sync_map_chunks(self, update: protocol.TerrainUpdate):
        for chunk in update.chunks:
            chunk_id = tuple(chunk.chunk_id)
            if chunk_id in self.cached_chunks:
                self.cached_chunks[tuple(chunk_id)].apply(chunk)
            else:
                self.cached_chunks[tuple(chunk_id)] = protocol.Chunk(chunk)
            draw.draw_chunk(self.chunks_image, self.cached_chunks[tuple(chunk_id)])


    async def listen(self):
        assert self.session is not None # TODO: connect()
        video = VideoWriter(
            "map_recording.avi",
            VideoWriter_fourcc(*"XVID"),
            20.0,
            (protocol.CHUNK_SIZE * 16, protocol.CHUNK_SIZE * 16),
        )
        self.chunks_image = PIL.Image.new("RGB", (protocol.CHUNK_SIZE * 16, protocol.CHUNK_SIZE * 16))
        self.hud_image = self.chunks_image
        guidance = 0
        try:
            async for msg in self.ws:
                msg = json.loads(msg)
                if "Game" in msg:
                    update = protocol.Update(msg["Game"])
                    if self.update_callback:
                        await self.update_callback(self, update)
                    await self.sync_map_chunks(cast(protocol.TerrainUpdate, update.terrain))
                    frame = self.encode_map_image(update)
                    video.write(frame)
                    imshow("Map", frame)
                    if waitKey(25) & 0xFF == ord('q'):
                        break
                   
                    logging.debug('received an update')
                    await self.control(
                        direction=math.radians(guidance), velocity=27
                    )
                    
                    if update.death_reason is not None:
                        logging.info(f"death: {update.death_reason}")

                        
                    if update.contacts is not None:
                        for decoded in update.contacts:
                            if decoded.header.player_id and decoded.player_id == self.session.player_id:
                                logging.info(f"player contact: {decoded}")
                                self.hud_image = self.chunks_image.copy()
                                self.hud_image.putpixel(decoded.position_to_terrain(), (255, 255, 255))
                            elif decoded.header.type and decoded.entity_type == "oilPlatform":
                                for i in range(-1, 2):
                                    for j in range(-1, 2):
                                        self.chunks_image.putpixel(decoded.position_to_terrain(), (255, 0, 0)) # TODO: structures_image?

                    
                else:
                    logging.debug(f'Unhandled message: {msg}')
                guidance += 1
        finally:
            video.release()
            destroyAllWindows()

    async def close(self):
        if self.ws is not None:
            await self.ws.close()


    async def open(self):
        # TODO: pyright auto close
        urlparams = dict(protocol=self.protocol)
        if self.session:
            urlparams["session_id"] = str(self.session.session_id)
            urlparams["arena_id"] = str(self.session.arena_id)
        self.cached_ws_endpoint = (
            self.ws_endpoint.format(
                server_id=self.session.server_id if self.session is not None else 1 # TODO: auto server resolve
            )
            + "/?"
            + urlencode(urlparams)
        )

        self.ws = await websockets.client.connect(self.cached_ws_endpoint)

    async def create_player(self, name: str | None = None):
        msg = await self.ws.recv()
        self.session = protocol.SessionCreated.decode(str(msg))

        if name is not None:
            await self.send(protocol.SetAlias(name))
  
    async def spawn(self, entity_type: str):
        await self.send(protocol.Spawn(entity_type=entity_type))
