"""Layout of a board message (Components V2). No network: builds objects only.

Layout per message (see D-010):
    Container
      TextDisplay   header: mode name, "更新于 <t:now:R>", page i/n
      Separator
      per entry: Section(TextDisplay(entry text), accessory=link Button)
    -> 3 + 3 * entries components; Discord allows 40 -> at most 12 entries.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

import discord
from discord import ui

from .models import Entry, Mode

MODE_NAMES = {Mode.RANKED: "排位", Mode.MATCH: "匹配", Mode.OTHER: "其他游戏"}
DEFAULT_REQUIREMENT = "组队中"

# Discord limits for a Components V2 message (D-010).
MAX_COMPONENTS = 40
MAX_TEXT_LENGTH = 4000
BUTTON_LABEL_LIMIT = 80
# (40 - container - header - separator) // 3 components per entry
MAX_ENTRIES_PER_MESSAGE = (MAX_COMPONENTS - 3) // 3
# Keeps a full page (12 entries, 20-digit IDs) under 4000 text characters.
REQUIREMENT_LIMIT = 150


@dataclass(frozen=True)
class RoomInfo:
    name: str
    member_count: int


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def effective_per_page(configured: int) -> int:
    """Clamp the configured page size to what one message can hold."""
    return max(1, min(configured, MAX_ENTRIES_PER_MESSAGE))


def entry_requirement(text: str) -> str:
    """One line of player text, markdown escaped, at most REQUIREMENT_LIMIT chars."""
    one_line = " ".join(text.split())
    if not one_line:
        return DEFAULT_REQUIREMENT
    with warnings.catch_warnings():
        # discord.py 2.7.1 passes re.sub's count positionally (deprecated in 3.13+).
        warnings.filterwarnings(
            "ignore", "'count' is passed as positional", DeprecationWarning
        )
        escaped = discord.utils.escape_markdown(one_line)
    return _truncate(escaped, REQUIREMENT_LIMIT)


def split_live_entries(
    entries: Iterable[Entry], room_exists: Callable[[int], bool]
) -> tuple[list[Entry], list[Entry]]:
    """(entries whose room still exists, entries whose room is gone), input order."""
    live: list[Entry] = []
    gone: list[Entry] = []
    for entry in entries:
        (live if room_exists(entry.room_id) else gone).append(entry)
    return live, gone


def card_url(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def room_url(guild_id: int, room_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{room_id}"


def entry_text(entry: Entry, guild_id: int) -> str:
    link = card_url(guild_id, entry.card_channel_id, entry.card_message_id)
    return (
        f"{entry_requirement(entry.text)}\n"
        f"<@{entry.host_id}> · <t:{int(entry.updated_at)}:R> · [查看卡片]({link})"
    )


def room_button_label(room: RoomInfo, show_count: bool) -> str:
    label = f"{room.member_count}人 @ {room.name}" if show_count else room.name
    return _truncate(label, BUTTON_LABEL_LIMIT)


def header_text(mode: Mode, now: float, page_index: int, total_pages: int) -> str:
    text = f"**{MODE_NAMES[mode]}** · 更新于 <t:{int(now)}:R>"
    if total_pages > 1:
        text += f" · {page_index + 1}/{total_pages}"
    return text


def build_board_view(
    mode: Mode,
    page: Sequence[Entry],
    page_index: int,
    total_pages: int,
    *,
    now: float,
    guild_id: int,
    rooms: Mapping[int, RoomInfo],
    empty_text: str,
    show_count: bool,
) -> ui.LayoutView:
    container: ui.Container = ui.Container(
        ui.TextDisplay(header_text(mode, now, page_index, total_pages)),
        ui.Separator(),
    )
    if not page:
        container.add_item(ui.TextDisplay(empty_text))
    for entry in page:
        text = ui.TextDisplay(entry_text(entry, guild_id))
        room = rooms.get(entry.room_id)
        if room is None:
            container.add_item(text)
            continue
        button: ui.Button = ui.Button(
            style=discord.ButtonStyle.link,
            label=room_button_label(room, show_count),
            url=room_url(guild_id, entry.room_id),
        )
        container.add_item(ui.Section(text, accessory=button))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
