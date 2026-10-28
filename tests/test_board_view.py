import discord
import pytest

from zaizai.board_view import (
    BUTTON_LABEL_LIMIT,
    MAX_ENTRIES_PER_MESSAGE,
    REQUIREMENT_LIMIT,
    RoomInfo,
    build_board_view,
    card_url,
    effective_per_page,
    entry_requirement,
    entry_text,
    header_text,
    room_button_label,
    room_url,
    split_live_entries,
)
from zaizai.models import Entry, Mode

BIG = 10**19  # 20-digit snowflakes: worst case for text length


def make_entry(i: int, text: str = "铂钻 3=2", big: bool = False) -> Entry:
    base = BIG if big else 0
    return Entry(
        id=i,
        room_id=base + 100 + i,
        mode=Mode.RANKED,
        text=text,
        host_id=base + 200 + i,
        card_channel_id=base + 300,
        card_message_id=base + 400 + i,
        created_at=1_700_000_000,
        updated_at=1_700_000_000 + i,
    )


def test_entry_requirement_defaults_and_truncates():
    assert entry_requirement("  铂钻 3=2 ") == "铂钻 3=2"
    assert entry_requirement("   ") == "组队中"
    long = entry_requirement("x" * 500)
    assert len(long) == REQUIREMENT_LIMIT
    assert long.endswith("…")


def test_urls():
    assert card_url(1, 2, 3) == "https://discord.com/channels/1/2/3"
    assert room_url(1, 9) == "https://discord.com/channels/1/9"


def test_entry_text_has_requirement_host_time_and_card_link():
    text = entry_text(make_entry(1), guild_id=7)
    assert text.splitlines()[0] == "铂钻 3=2"
    assert "<@201>" in text
    assert "<t:1700000001:R>" in text
    assert "(https://discord.com/channels/7/300/401)" in text


def test_room_button_label():
    assert room_button_label(RoomInfo("排位 3", 4), show_count=True) == "4人 @ 排位 3"
    assert room_button_label(RoomInfo("排位 3", 4), show_count=False) == "排位 3"
    long = room_button_label(RoomInfo("房" * 200, 4), show_count=True)
    assert len(long) == BUTTON_LABEL_LIMIT


def test_header_text():
    assert header_text(Mode.RANKED, 1000.9, 0, 1) == "**排位** · 更新于 <t:1000:R>"
    assert header_text(Mode.MATCH, 1000, 1, 3) == "**匹配** · 更新于 <t:1000:R> · 2/3"
    assert header_text(Mode.OTHER, 1000, 0, 1).startswith("**其他游戏**")


def test_effective_per_page_clamps():
    assert effective_per_page(10) == 10
    assert effective_per_page(99) == MAX_ENTRIES_PER_MESSAGE
    assert effective_per_page(0) == 1


def _texts(view):
    return [
        item.content
        for item in view.walk_children()
        if isinstance(item, discord.ui.TextDisplay)
    ]


def _buttons(view):
    return [i for i in view.walk_children() if isinstance(i, discord.ui.Button)]


def test_empty_page_shows_empty_text():
    view = build_board_view(
        Mode.RANKED, [], 0, 1, now=1000, guild_id=7, rooms={},
        empty_text="当前没有活跃的信息。", show_count=True,
    )
    assert "当前没有活跃的信息。" in _texts(view)
    assert _buttons(view) == []


def test_entries_get_link_button_to_room():
    entries = [make_entry(1), make_entry(2)]
    rooms = {101: RoomInfo("排位 1", 3), 102: RoomInfo("排位 2", 5)}
    view = build_board_view(
        Mode.RANKED, entries, 0, 1, now=1000, guild_id=7, rooms=rooms,
        empty_text="-", show_count=True,
    )
    buttons = _buttons(view)
    assert [b.label for b in buttons] == ["3人 @ 排位 1", "5人 @ 排位 2"]
    assert buttons[0].url == "https://discord.com/channels/7/101"
    assert all(b.style is discord.ButtonStyle.link for b in buttons)


def test_entry_without_room_info_has_no_button():
    view = build_board_view(
        Mode.RANKED, [make_entry(1)], 0, 1, now=1000, guild_id=7, rooms={},
        empty_text="-", show_count=True,
    )
    assert _buttons(view) == []
    assert any("铂钻 3=2" in t for t in _texts(view))


@pytest.mark.parametrize("show_count", [True, False])
def test_full_page_worst_case_fits_discord_limits(show_count):
    entries = [
        make_entry(i, text="字" * 1000, big=True)
        for i in range(MAX_ENTRIES_PER_MESSAGE)
    ]
    rooms = {e.room_id: RoomInfo("房" * 100, 99) for e in entries}
    view = build_board_view(
        Mode.OTHER, entries, 98, 99, now=BIG, guild_id=BIG, rooms=rooms,
        empty_text="-", show_count=show_count,
    )
    assert view.total_children_count <= 40
    assert view.content_length() <= 4000
    assert len(_buttons(view)) == MAX_ENTRIES_PER_MESSAGE


def test_entry_text_escapes_markdown_and_newlines():
    text = entry_text(make_entry(1, text="# 标题\r\n**粗** _x_"), guild_id=7)
    first, second = text.split("\n")
    assert first == r"\# 标题 \*\*粗\*\* \_x\_"
    assert second.startswith("<@201>")


def test_entry_text_escaped_requirement_stays_within_limit():
    text = entry_text(make_entry(1, text="*" * 500), guild_id=7)
    assert len(text.split("\n")[0]) == REQUIREMENT_LIMIT


def test_split_live_entries():
    entries = [make_entry(1), make_entry(2), make_entry(3)]
    live, gone = split_live_entries(entries, lambda room_id: room_id != 102)
    assert [e.id for e in live] == [1, 3]
    assert [e.id for e in gone] == [2]
