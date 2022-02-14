from dataclasses import dataclass, field
import dataclasses
import functools
import json
import math
from types import FunctionType
from typing import Any, Tuple, Union
from hilbertcurve.hilbertcurve import HilbertCurve
import rle

CHUNK_SIZE = 64
HILBERT_CURVE = HilbertCurve(p=int(math.log2(CHUNK_SIZE)), n=2, n_procs=0)


def _dict_drop_nulls(src: dict) -> dict:
    return {k: v for k, v in src.items() if v is not None}


def encode_message(self, skip_null=True) -> str:
    name = type(self).__name__
    if hasattr(self, '__message__'):
        name = self.__message__()

    if dataclasses.is_dataclass(self):
        self = dataclasses.asdict(self)
    elif hasattr(self, '__encode__'):
        self = self.__encode__()

    if skip_null:
        self = _dict_drop_nulls(self)

    return json.dumps({name: self})


def decode_message(cls, msg: str) -> Union[dict, Any]:
    decoded = json.loads(msg)[cls.__message__() if hasattr(cls, '__message__'
                                                           ) else cls.__name__]
    if dataclasses.is_dataclass(cls):
        return cls(**decoded)
    elif hasattr(cls, '__decode__'):
        return cls.__decode__(decoded)

    return json.loads(decoded)


def _set_class_method(cls, val, name=None):
    if name is None:
        name = val.__name__
    if isinstance(val, FunctionType):
        val.__qualname__ = f"{cls.__qualname__}.{name}"
    setattr(cls, name, val)


def message(cls=None, name=None):
    if not callable(cls):
        return functools.partial(message, name=cls)

    _set_class_method(cls, encode_message, name='encode')
    _set_class_method(cls,
                      staticmethod(lambda msg: decode_message(cls, msg)),
                      name='decode')
    if name is not None:
        _set_class_method(cls, staticmethod(lambda: name), name='__message__')

    return cls


@message
@dataclass
class CreateSession:
    game_id: str = ''
    saved_session_tuple: Tuple[int, int] = None


@message
@dataclass
class SessionCreated:
    arena_id: int
    session_id: int
    player_id: int
    server_id: int = field(default=1)


@message
@dataclass
class IdentifySession:
    alias: str


@message
@dataclass
class SendChat:
    message: str
    whisper: bool = False


@message
@dataclass
class Spawn:
    entity_type: str


class ContactHeader:
    HEADER_POSITIONS = [
        'velocity', 'altitude', 'direction_target', 'velocity_target',
        'damage', 'type', 'player_id', 'reloads'
    ]
    POSITIONS = {v: i for i, v in enumerate(HEADER_POSITIONS)}

    def __init__(self, bits: int):
        for i in range(len(self.HEADER_POSITIONS)):
            setattr(self, self.HEADER_POSITIONS[i], bool(bits & (1 << i)))

    def __repr__(self) -> str:
        flags = ', '.join(
            [v + "=True" for v in self.HEADER_POSITIONS if getattr(self, v)])
        return f'ContactHeader({flags})'


class Contact:

    def __init__(self, header: int, data: list):
        self.header = ContactHeader(header)

        self.id = data[0]
        self.position = data[1]
        self.direction = data[2]
        data = data[3:]

        i = 0
        for p in self.header.HEADER_POSITIONS:
            setattr(self, p, data[i] if getattr(self.header, p) else None)
            if getattr(self.header, p):
                i += 1

    def __repr__(self) -> str:
        params = ', '.join([
            k + "=" + format(v) for k, v in vars(self).items() if v is not None
        ])

        return f'ContactHeader({params})'


class ChunkUpdate:
    # LAND_ALTITUDE = 15
    # ALTITUDE_STR = {}

    def __init__(self, chunk, chunk_data: dict):
        self.chunk = chunk
        self.is_update = chunk_data['is_update']
        self.bytes = chunk_data['bytes']
        self.cached_altitudes = None

    def _decode_positioned_pixel(self, byte):
        return (((byte >> 10) & 0xff, ((byte >> 4) % 64) & 0xff),
                ((byte % 16) & 0xff) << 4)

    def _decode_pixel(self, byte) -> tuple:
        return (byte & 0xf, (byte >> 4) & 0xf)

    @property
    def altitudes(self):
        if self.cached_altitudes is not None:
            return self.cached_altitudes

        if not self.is_update:
            self.cached_altitudes = [[0 for _ in range(CHUNK_SIZE)]
                                     for _ in range(CHUNK_SIZE)]
            # 0, 1
            # 2, 3
            # 4, 5
            # 6, 7
            bytes = rle.decode([b & 0xf for b in self.bytes],
                               [(b & 0xf) + 1 for b in self.bytes])
            for i, v in enumerate(bytes):
                point = HILBERT_CURVE.point_from_distance(i)
                self.cached_altitudes[point[0]][point[1]] = v
            return self.cached_altitudes

        for v in self.bytes:
            self.cached_altitudes = [[0 for _ in range(CHUNK_SIZE)]
                                     for _ in range(CHUNK_SIZE)]
            (x, y), d = self._decode_positioned_pixel(v)
            self.cached_altitudes[y][x] = d

        return self.cached_altitudes

    def print(self):
        print(self.is_update)
        shades = [' ', '-']
        for i in range(CHUNK_SIZE):
            for j in range(CHUNK_SIZE):
                v = self.cached_altitudes[i][j] << 4 > 127
                print(shades[v], end='')
            print()


class TerrainUpdate:

    def __init__(self, data):
        # is_update = True
        # x = byte >> 10
        # y = byte >> 4
        # value = byte & 0
        self.chunks = [ChunkUpdate(chunk, update) for [chunk, update] in data]


class Update:

    def __init__(self, msg: dict):
        self.contacts = [
            Contact(header=header, data=c) for (header, c) in msg['contacts']
        ]
        self.terrain = TerrainUpdate(msg['terrain'])

        self.score = msg['score']
        self.world_radius = msg['world_radius']

        pass
