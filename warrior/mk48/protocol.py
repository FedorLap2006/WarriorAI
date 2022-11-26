from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import dataclasses
import functools
import json
import math
from types import FunctionType
import types
from typing import Any, Generic, NamedTuple, Optional, Tuple, TypeVar, Union, cast
from hilbertcurve.hilbertcurve import HilbertCurve
import rle

CHUNK_SIZE = 64
HILBERT_CURVE = HilbertCurve(p=int(math.log2(CHUNK_SIZE)), n=2, n_procs=0)


def _dict_drop_nulls(src: dict) -> dict:
    if not isinstance(src, dict):
        return src
    return {k: _dict_drop_nulls(v) for k, v in src.items() if v is not None}


def encode_message(self, kind: str | None, skip_null=True) -> str:
    name = type(self).__name__
    if hasattr(self, "__message__"):
        name = self.__message__()

    if hasattr(self, "__encode__"):
        self = self.__encode__()
    elif dataclasses.is_dataclass(self):
        self = dataclasses.asdict(self)

    if skip_null:
        self = _dict_drop_nulls(self)

    if kind is not None:
        return json.dumps({kind: {name: self}})
    else:
        return json.dumps({name: self})


def decode_message(cls, kind: str | None, msg: str) -> Union[dict, Any]:
    decoded = json.loads(msg)
    if kind is not None:
        decoded = decoded[kind]

    # print(decoded, kind)
    decoded = decoded[
        cls.__message__() if hasattr(cls, "__message__") else cls.__name__
    ]
    if hasattr(cls, "__decode__"):
        return cls.__decode__(decoded)
    elif dataclasses.is_dataclass(cls):
        return cls(**decoded)

    return json.loads(decoded)


def _set_class_method(cls, val, name=None):
    if name is None:
        name = val.__name__
    if isinstance(val, FunctionType):
        val.__qualname__ = f"{cls.__qualname__}.{name}"
    setattr(cls, name, val)


def message(cls, *args, **kwargs):
    if cls is None:
        return functools.partial(_message, **kwargs)
    if not callable(cls):
        return lambda cls_: _message(cls_, cls, *args, **kwargs)
    return _message(cls)


def _message(
    cls,
    kind: str | None = None,
    name: str | None = None,
):
    _set_class_method(
        cls,
        lambda self, *args, **kwargs: encode_message(self, kind, *args, **kwargs),
        name="encode",
    )
    _set_class_method(
        cls,
        staticmethod(
            lambda msg, *args, **kwargs: decode_message(cls, kind, msg, *args, **kwargs)
        ),
        name="decode",
    )
    if name is not None:
        _set_class_method(cls, staticmethod(lambda: name), name="__message__")

    return cls

_MT = TypeVar('_MT')

class MessageBase(Generic[_MT]):
    @staticmethod
    @abstractmethod
    def decode(msg: str) -> _MT:
        pass

    @abstractmethod
    def encode() -> str:
        pass

@message("Client")
@dataclass
class SessionCreated(MessageBase['SessionCreated']):
    arena_id: int
    cohort_id: int
    session_id: int
    player_id: int
    server_id: int = field(default=1)


@message("Client")
@dataclass
class SetAlias(MessageBase['SetAlias']):
    alias: str

    def __encode__(self):
        return self.alias

    @staticmethod
    def __decode__(decoded):
        return SetAlias(alias=decoded)


@message("Chat", "Send")
@dataclass
class SendChat(MessageBase['SendChat']):
    message: str
    whisper: bool = False


@message("Game")
@dataclass
class Spawn(MessageBase['Spawn']):
    entity_type: str


@message
@dataclass
class Guidance(MessageBase['Guidance']):
    velocity_target: Optional[int] = None
    direction_target: Optional[float] = None


@message("Game")
@dataclass
class Control(MessageBase['Control']):
    guidance: Optional[Guidance] = None
    aim_target: Optional[tuple[float, float]] = None
    active: bool = True
    submerge: bool = False
    pay: object = None
    hint: object = None


class Coords(NamedTuple):
    x: float
    y: float


class TerrainCoords(NamedTuple):
    x: int
    y: int

    @staticmethod
    def from_real(c: Coords) -> "TerrainCoords":
        return TerrainCoords(
            int(round(c.x / 25.0 + 8 * CHUNK_SIZE)),
            int(round(c.y / 25.0 + 8 * CHUNK_SIZE)),
        )

    def to_real(self) -> Coords:
        return Coords(self.x * 25.0 - 8 * CHUNK_SIZE, self.y * 25.0 - 8 * CHUNK_SIZE)


class ContactHeader:
    velocity: bool
    altitude: bool
    direction_target: bool
    velocity_target: bool
    damage: bool
    type: bool
    player_id: bool
    reloads: bool


    HEADER_POSITIONS = [
        "velocity",
        "altitude",
        "direction_target",
        "velocity_target",
        "damage",
        "type",
        "player_id",
        "reloads",
    ]

    # HEADER_POSITIONS = [
    #     "velocity",
    #     "altitude",
    #     "direction_target",
    #     "velocity_target",
    #     "damage",
    #     "type",
    #     "player_id",
    #     "reloads",
    # ]

    POSITIONS = {v: i for i, v in enumerate(HEADER_POSITIONS)}

    def __init__(self, bits: int):
        for i in range(len(self.HEADER_POSITIONS)):
            setattr(self, self.HEADER_POSITIONS[i], bool(bits & (1 << i)))

    def __repr__(self) -> str:
        flags = ", ".join(
            [v + "=True" for v in self.HEADER_POSITIONS if getattr(self, v)]
        )
        return f"ContactHeader({flags})"


class Contact:
    transform: Any | None
    altitude: int | None
    guidance: Guidance | None
    damage: int | None
    entity_type: str | None
    player_id: int | None
    reloads: Any | None # TODO: reloads
    turrets: Any | None # TODO: turrets

    def __init__(self, header: int, data: list):
        self.header = ContactHeader(header)

        self.id = data[0]
        self.position = Coords(*data[1])
        self.direction = data[2]
        data = data[3:]

        i = 0
        for p in self.header.HEADER_POSITIONS: # TODO: they differ now
            if not getattr(self.header, p):
                continue
            match p:
                case "velocity":
                    # TODO: transform
                    pass
                case "direction_target", "velocity_target":
                    self.direction = Guidance()
                    setattr(self.direction, p, data[i])
                case "type":
                    self.entity_type = data[i]
                case _:
                   setattr(self, p, data[i] if getattr(self.header, p) else None)
            i += 1

        # i = 0
        # for p in self.header.HEADER_POSITIONS: # TODO: they differ now
        #     setattr(self, p, data[i] if getattr(self.header, p) else None)
        #     if getattr(self.header, p):
        #         i += 1

    def position_to_terrain(self) -> TerrainCoords:
        return TerrainCoords.from_real(self.position)

    def __repr__(self) -> str:
        params = ", ".join(
            [k + "=" + format(v) for k, v in vars(self).items() if v is not None]
        )

        return f"ContactHeader({params})"


class ChunkUpdate:
    # LAND_ALTITUDE = 15
    # ALTITUDE_STR = {}

    def __init__(self, chunk_id, chunk_data: dict):
        self.chunk_id = chunk_id
        self.is_update = chunk_data["is_update"]
        self.bytes = chunk_data["bytes"]
        self.cached_altitudes = None

    @staticmethod
    def decode_positioned_altitude(byte) -> tuple[TerrainCoords, int]:
        return (
            TerrainCoords((byte >> 10) & 0xFF, ((byte >> 4) % 64) & 0xFF),
            ((byte % 16) & 0xFF) << 4,
        )

    @staticmethod
    def decode_chunk(bytes):
        return rle.decode([b & 0xF0 for b in bytes], [(b & 0xF) + 1 for b in bytes])

    def calc_altitudes(self):
        if self.is_update:
            return

        altitudes = [[0 for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        bytes = self.decode_chunk(self.bytes)
        for i, v in enumerate(bytes):
            point = list(HILBERT_CURVE.point_from_distance(i))
            altitudes[point[0]][point[1]] = v
        return altitudes

    @property
    def altitudes(self) -> list[list[int]]:
        if self.is_update:
            return []
        if self.cached_altitudes is None:
            self.cached_altitudes = self.calc_altitudes()

        return cast(list[list[int]], self.cached_altitudes)

    @property
    def partial_altitudes(self) -> list[tuple[TerrainCoords, int]]:  # TODO
        if not self.is_update:
            return []

        altitudes = []
        for v in self.bytes:
            (x, y), d = self.decode_positioned_altitude(v)
            altitudes.append((TerrainCoords(x, y), d))

        return altitudes

    def print(self):
        # TODO: calculate
        if self.cached_altitudes is None:
            return
        print(self.is_update)
        shades = [" ", "-"]
        for i in range(CHUNK_SIZE):
            for j in range(CHUNK_SIZE):
                v = self.cached_altitudes[i][j] > 128
                print(shades[v], end="")
            print()


class Chunk:
    def __init__(self, update: ChunkUpdate):
        self.chunk_id = update.chunk_id
        self.altitudes = update.altitudes
        pass

    def apply(self, update: ChunkUpdate):
        if not update.is_update:
            return

        for (coords, alt) in update.partial_altitudes:
            self.altitudes[coords.x][coords.y] = alt


class TerrainUpdate:
    def __init__(self, data):
        # is_update = True
        # x = byte >> 10
        # y = byte >> 4
        # value = byte & 0
        self.chunks = [ChunkUpdate(chunk, update) for [chunk, update] in data]


class Update:
    contacts: list[Contact] | None
    world_radius: float | None
    def __init__(self, msg: dict):
        self.contacts = None
        if "contacts" in msg:
            self.contacts = [
                Contact(header=header, data=c) for (header, c) in msg["contacts"]
            ]

        self.terrain = None
        if "terrain" in msg:
            self.terrain = TerrainUpdate(msg["terrain"])

        self.score = None
        if "score" in msg:
            self.score = msg["score"]

        self.world_radius = None
        if "world_radius" in msg:
            self.world_radius = msg["world_radius"]

        self.death_reason = None
        if "death_reason" in msg:
            self.death_reason = msg["death_reason"]
        pass
