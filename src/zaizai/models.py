from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    RANKED = "ranked"
    MATCH = "match"
    OTHER = "other"


@dataclass(frozen=True)
class Room:
    id: int
    mode: Mode
    owner_id: int
    category_id: int
    created_at: float
    locked: bool
    panel_message_id: int | None


@dataclass(frozen=True)
class Entry:
    id: int
    room_id: int
    mode: Mode
    text: str
    host_id: int
    card_channel_id: int
    card_message_id: int
    created_at: float
    updated_at: float
