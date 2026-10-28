"""Live LFG board: one (or, when paginated, several) edited-in-place message per mode."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Hashable, Mapping, Sequence

import discord
from discord.ext import commands, tasks

from ..asyncutil import Debouncer
from ..board_sync import sync_board
from ..board_view import (
    RoomInfo,
    build_board_view,
    effective_per_page,
    split_live_entries,
)
from ..bot import discord_call
from ..config import mode_in_scope
from ..entries import find_expired, paginate_entries, sort_for_board
from ..models import Entry, Mode

log = logging.getLogger(__name__)

CLEANUP_INTERVAL_SEC = 60


class DiscordBoardGateway:
    """BoardGateway backed by the board channel; built fresh for each refresh."""

    def __init__(
        self,
        channel: discord.abc.Messageable,
        *,
        guild_id: int,
        rooms: Mapping[int, RoomInfo],
        total_pages: int,
        empty_text: str,
        show_count: bool,
    ) -> None:
        self._channel = channel
        self._guild_id = guild_id
        self._rooms = rooms
        self._total_pages = total_pages
        self._empty_text = empty_text
        self._show_count = show_count

    def _view(self, mode: Mode, page: Sequence[Entry], page_index: int):
        return build_board_view(
            mode,
            page,
            page_index,
            self._total_pages,
            now=time.time(),
            guild_id=self._guild_id,
            rooms=self._rooms,
            empty_text=self._empty_text,
            show_count=self._show_count,
        )

    async def exists(self, message_id: int) -> bool:
        try:
            await discord_call(lambda: self._channel.fetch_message(message_id))
        except discord.NotFound:
            return False
        return True

    async def send(self, mode: Mode, page: list[Entry], page_index: int) -> int:
        view = self._view(mode, page, page_index)
        message = await discord_call(
            lambda: self._channel.send(
                view=view, allowed_mentions=discord.AllowedMentions.none()
            )
        )
        return message.id

    async def edit(
        self, message_id: int, mode: Mode, page: list[Entry], page_index: int
    ) -> None:
        view = self._view(mode, page, page_index)
        partial = self._channel.get_partial_message(message_id)
        await discord_call(
            lambda: partial.edit(
                view=view, allowed_mentions=discord.AllowedMentions.none()
            )
        )

    async def delete(self, message_id: int) -> None:
        try:
            await discord_call(self._channel.get_partial_message(message_id).delete)
        except discord.NotFound:
            pass


class Board(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.cfg = bot.cfg
        self.store = bot.store
        self._locks: dict[Mode, asyncio.Lock] = {}
        self._debouncer = Debouncer(self.cfg.board_refresh_debounce_sec, self._refresh)
        self._ready_done = False

    def _modes(self) -> list[Mode]:
        """In-scope modes with a command; a disabled mode can never have entries."""
        return [
            m
            for m, mc in self.cfg.modes.items()
            if mode_in_scope(self.cfg, m) and mc.command
        ]

    def _live_entries(self, mode: Mode, guild: discord.Guild | None) -> list[Entry]:
        """Delete entries whose room is gone (store or guild); return the rest."""

        def room_exists(room_id: int) -> bool:
            if self.store.get_room(room_id) is None:
                return False
            return guild is None or guild.get_channel(room_id) is not None

        live, gone = split_live_entries(self.store.list_entries(mode), room_exists)
        for entry in gone:
            self.store.delete_entry_by_room(entry.room_id)
        return live

    async def cog_load(self) -> None:
        self.cleanup_loop.start()

    async def cog_unload(self) -> None:
        self.cleanup_loop.cancel()
        await self._debouncer.aclose()

    # -- events ----------------------------------------------------------
    @commands.Cog.listener()
    async def on_board_dirty(self, mode: Mode) -> None:
        if mode in self._modes():
            self._debouncer.trigger(mode)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._ready_done:
            return
        self._ready_done = True
        for mode in self._modes():
            self._debouncer.trigger(mode)

    # -- refresh ---------------------------------------------------------
    async def _refresh(self, mode: Hashable) -> None:
        assert isinstance(mode, Mode)
        # The debouncer may start a new run while the previous one is still
        # editing; overlapping sync_board runs would double-send messages.
        lock = self._locks.setdefault(mode, asyncio.Lock())
        async with lock:
            try:
                await self._sync(mode)
            except Exception as e:
                await self.bot.report_error(e, f"board.refresh({mode.value})")

    async def _sync(self, mode: Mode) -> None:
        if not self.cfg.board_channel_id:
            log.warning("board.board_channel_id is 0; not posting the %s board", mode.value)
            return
        guild = self.bot.get_guild(self.cfg.guild_id)
        if guild is None:
            log.warning("guild %s not available; skipping board refresh", self.cfg.guild_id)
            return
        channel = self.bot.get_channel(self.cfg.board_channel_id)
        if channel is None:
            channel = await discord_call(
                lambda: self.bot.fetch_channel(self.cfg.board_channel_id)
            )

        live = self._live_entries(mode, guild)
        rooms: dict[int, RoomInfo] = {}
        for entry in live:
            voice = guild.get_channel(entry.room_id)
            assert voice is not None  # checked by _live_entries
            rooms[entry.room_id] = RoomInfo(
                voice.name, len(getattr(voice, "members", []))
            )

        pages = paginate_entries(
            sort_for_board(live),
            per_page=effective_per_page(self.cfg.board_max_entries_per_message),
        )
        gateway = DiscordBoardGateway(
            channel,
            guild_id=guild.id,
            rooms=rooms,
            total_pages=len(pages),
            empty_text=self.cfg.board_empty_text,
            show_count=self.cfg.board_show_member_count,
        )
        await sync_board(self.store, gateway, mode, pages)

    # -- expiry ----------------------------------------------------------
    @tasks.loop(seconds=CLEANUP_INTERVAL_SEC)
    async def cleanup_loop(self) -> None:
        try:
            self._cleanup()
        except Exception as e:
            await self.bot.report_error(e, "board.cleanup")

    @cleanup_loop.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    def _cleanup(self) -> None:
        """Drop entries of vanished rooms and timed-out entries; cards are kept."""
        now = time.time()
        guild = self.bot.get_guild(self.cfg.guild_id)
        for mode in self._modes():
            before = len(self.store.list_entries(mode))
            live = self._live_entries(mode, guild)
            expired = find_expired(live, now, self.cfg.board_entry_timeout_min)
            for entry in expired:
                self.store.delete_entry_by_room(entry.room_id)
            removed = before - len(live) + len(expired)
            if removed:
                log.info("removed %d stale %s board entries", removed, mode.value)
                self.bot.dispatch("board_dirty", mode)


async def setup(bot) -> None:
    await bot.add_cog(Board(bot))
