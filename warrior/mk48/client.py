import asyncio
import json
import random
import websockets

from . import endpoints, protocol


class Client:
    """Session is the event dispatcher of game events"""

    session: protocol.SessionCreated

    def __init__(self,
                 metadata_endpoint: str = endpoints.ENDPOINT_META_WS,
                 session_endpoint: str = endpoints.ENDPOINT_SESSION_WS):
        self.meta_ws_endpoint = metadata_endpoint + "?format=json"
        self.session_ws_endpoint = session_endpoint + "?format=json"

        self.meta_ws = None
        self.session_ws = None

    async def listen_metadata(self):
        # print('listening hello')
        async for msg in self.meta_ws:
            pass

    async def listen_session(self):
        # print('listening session')
        async for msg in self.session_ws:
            msg = json.loads(msg)
            if 'terrain' in list(msg.keys()):
                tu = protocol.TerrainUpdate(msg['terrain'])
                print([c.chunk for c in tu.chunks])
                for c in tu.chunks:
                    if c.is_update:
                        continue
                    print(c.chunk)
                    c.altitudes
                    c.print()
                    print('======================================')

            if list(msg.keys())[0] == 'contacts':
                for c in msg['contacts']:
                    [header, data] = c
                    decoded = protocol.Contact(header=header, data=data)
                    if decoded.header.player_id and decoded.player_id == self.session.player_id:
                        print(decoded)

            #     # for v in msg['terrain']:
            #     #     if v[1]['is_update']:
            #     #         print(v)

    async def close(self):
        if self.session_ws is not None:
            await self.session_ws.close()
        if self.meta_ws is not None:
            await self.meta_ws.close()

    async def init_session(self):
        if self.session is None:
            raise ValueError(
                'Session is not initialised. Call init_player to initialise it.'
            )
        if self.session_ws is not None:
            self.session_ws.close()
        # print(
        # self.session_ws_endpoint.format(
        #     server_id=self.session.server_id,
        #     session_id=self.session.session_id))
        self.session_ws = await websockets.connect(
            self.session_ws_endpoint.format(server_id=self.session.server_id,
                                            session_id=self.session.session_id)
        )

    async def init_player(self, name: str = None):
        if self.meta_ws is not None:
            await self.meta_ws.close()
        self.meta_ws = await websockets.connect(self.meta_ws_endpoint)
        await self.meta_ws.send(
            protocol.CreateSession(game_id='Mk48').encode())
        # print('ok')
        self.session = protocol.SessionCreated.decode(await
                                                      self.meta_ws.recv())
        # print('umm')

        if name is not None:
            await self.meta_ws.send(
                protocol.IdentifySession(alias=name).encode())

    async def spawn(self, entity_type: str):
        await self.session_ws.send(
            protocol.Spawn(entity_type=entity_type).encode())
        await asyncio.sleep(1)
        await self.meta_ws.send(
            protocol.SendChat(
                random.choice([
                    'Hello, this is test!', 'Beep boop beep', 'Pog', 'Woah',
                    'Hello everyone!'
                ])).encode())
