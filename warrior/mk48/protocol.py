from dataclasses import dataclass, field
import dataclasses
import functools
import json
from types import FunctionType
from typing import Any, Tuple, Union


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
