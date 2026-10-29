"""Join-to-create temporary voice rooms."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import discord
from discord.ext import commands

from ..asyncutil import SerialQueue
from ..bot import discord_call
from ..config import mode_in_scope
from ..models import Mode, Room
from ..placement import next_room_name, pick_category
from ..reconcile import partition_stale, reconcile

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Transition:
    entrance_joined: int | None  # entrance channel id the member just joined
    left_room: int | None  # managed room the member left
    joined_room: int | None  # managed room the member joined


def classify_transition(
    before_id: int | None,
    after_id: int | None,
    entrance_ids: Collection[int],
    room_ids: Collection[int],
) -> Transition:
    """Decide what a voice state change means for entrances and managed rooms."""
    if before_id == after_id:
        return Transition(None, None, None)
    return Transition(
        entrance_joined=after_id if after_id in entrance_ids else None,
        left_room=before_id if before_id in room_ids else None,
        joined_room=after_id if after_id in room_ids else None,
    )


def entry_channel_changes(
    before_id: int | None,
    after_id: int | None,
    room_ids: Collection[int],
) -> tuple[int | None, int | None]:
    """(left, joined) voice channels that are not managed temp rooms.

    Such channels can still carry a board entry (D-014); temp rooms are
    handled by classify_transition.
    """
    if before_id == after_id:
        return (None, None)
    left = before_id if before_id is not None and before_id not in room_ids else None
    joined = after_id if after_id is not None and after_id not in room_ids else None
    return (left, joined)


def exclude_unmanaged(
    live: Mapping[int, int],
    entrance_ids: Collection[int],
    tracked_elsewhere: Collection[int],
) -> dict[int, int]:
    """Drop entrance channels and rooms tracked under other modes from live rooms."""
    skip = set(entrance_ids) | set(tracked_elsewhere)
    return {cid: n for cid, n in live.items() if cid not in skip}


def overflow_category_name(base_name: str, existing_count: int) -> str:
    """Name for the next overflow category: 'Base 2', 'Base 3', ..."""
    return f"{base_name} {existing_count + 1}"


def ordered_categories(configured: Sequence[int], stored: Sequence[int]) -> list[int]:
    """Categories in order of use: the configured ones first (as listed),
    then overflow categories the bot created itself."""
    seen = set(configured)
    return list(configured) + [c for c in stored if c not in seen]


class VoiceRooms(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.cfg = bot.cfg
        self.store = bot.store
        self.queue = SerialQueue(self.cfg.voice_create_queue_interval_ms)
        self._timers: dict[int, asyncio.Task[None]] = {}
        self._reconcile_lock = asyncio.Lock()

    # -- helpers ---------------------------------------------------------
    def _modes(self) -> list[Mode]:
        return [m for m in self.cfg.modes if mode_in_scope(self.cfg, m)]

    def _entrances(self) -> dict[int, Mode]:
        return {
            mc.entrance_channel_id: m
            for m, mc in self.cfg.modes.items()
            if mode_in_scope(self.cfg, m) and mc.entrance_channel_id != 0
        }

    def _seed_categories(self) -> None:
        # Every configured category is recorded (re-adding is a no-op), so
        # categories added to the config later are picked up on restart.
        for m in self._modes():
            for cat in self.cfg.modes[m].category_ids:
                self.store.add_category(m, cat)

    def _categories(self, mode: Mode) -> list[int]:
        return ordered_categories(
            self.cfg.modes[mode].category_ids, self.store.list_categories(mode)
        )

    async def cog_load(self) -> None:
        self._seed_categories()

    async def cog_unload(self) -> None:
        tasks = list(self._timers.values())
        self._timers.clear()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # -- events ----------------------------------------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        try:
            await self._handle_voice_update(member, before, after)
        except Exception as e:
            await self.bot.report_error(e, "voice_rooms.on_voice_state_update")

    async def _handle_voice_update(self, member, before, after) -> None:
        b = before.channel.id if before.channel else None
        a = after.channel.id if after.channel else None
        entrances = self._entrances()
        rooms = {r.id: r for r in self.store.list_rooms()}
        t = classify_transition(b, a, entrances.keys(), rooms.keys())

        # Member counts only show on the board for rooms with an entry.
        if t.left_room is not None:
            room = rooms[t.left_room]
            if self.store.get_entry_by_room(room.id) is not None:
                self.bot.dispatch("board_dirty", room.mode)
            if before.channel is not None and not before.channel.members:
                self._on_room_empty(room)
        if t.joined_room is not None:
            self._cancel_timer(t.joined_room)
            if self.store.get_entry_by_room(t.joined_room) is not None:
                self.bot.dispatch("board_dirty", rooms[t.joined_room].mode)
        if t.entrance_joined is not None:
            await self._create_room(member, entrances[t.entrance_joined])
        self._update_unmanaged_entries(before.channel, after.channel, rooms.keys())

    def _update_unmanaged_entries(self, before_ch, after_ch, room_ids) -> None:
        """Non-temp voice channels with an entry (D-014): refresh the member
        count; drop the entry once the channel is empty. The channel itself
        is never touched."""
        left, joined = entry_channel_changes(
            before_ch.id if before_ch else None,
            after_ch.id if after_ch else None,
            room_ids,
        )
        if left is not None:
            entry = self.store.get_entry_by_room(left)
            if entry is not None:
                if self.cfg.board_remove_when_room_empty and not before_ch.members:
                    self.store.delete_entry_by_room(left)
                self.bot.dispatch("board_dirty", entry.mode)
        if joined is not None:
            entry = self.store.get_entry_by_room(joined)
            if entry is not None:
                self.bot.dispatch("board_dirty", entry.mode)

    def _on_room_empty(self, room: Room) -> None:
        if self.cfg.board_remove_when_room_empty:
            if self.store.delete_entry_by_room(room.id):
                self.bot.dispatch("board_dirty", room.mode)
        self._start_timer(room)

    # -- empty timers ----------------------------------------------------
    def _cancel_timer(self, room_id: int) -> None:
        task = self._timers.pop(room_id, None)
        if task is not None:
            task.cancel()

    def _start_timer(self, room: Room) -> None:
        self._cancel_timer(room.id)
        task = asyncio.get_running_loop().create_task(self._delete_after_delay(room))
        self._timers[room.id] = task

        def _done(t: asyncio.Task[None], rid: int = room.id) -> None:
            if self._timers.get(rid) is t:
                del self._timers[rid]

        task.add_done_callback(_done)

    async def _delete_after_delay(self, room: Room) -> None:
        try:
            await asyncio.sleep(self.cfg.voice_empty_delete_delay_sec)
            channel = self.bot.get_channel(room.id)
            if channel is not None and getattr(channel, "members", None):
                return
            if channel is not None:
                try:
                    await self.queue.run(lambda: discord_call(channel.delete))
                except discord.NotFound:
                    pass
            self.store.delete_room(room.id)
            self.store.delete_entry_by_room(room.id)
            self.bot.dispatch("board_dirty", room.mode)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await self.bot.report_error(e, "voice_rooms.delete_empty_room")

    # -- creation --------------------------------------------------------
    async def _create_room(self, member: discord.Member, mode: Mode) -> None:
        guild = member.guild
        entrance_id = self.cfg.modes[mode].entrance_channel_id

        channel = await self.queue.run(lambda: self._make_channel(guild, mode))
        if channel is None:
            return

        still_there = (
            member.voice is not None
            and member.voice.channel is not None
            and member.voice.channel.id == entrance_id
        )
        if not still_there:
            await self._discard(channel)
            return

        room = Room(
            id=channel.id,
            mode=mode,
            owner_id=member.id,
            category_id=channel.category_id or 0,
            created_at=time.time(),
            locked=False,
            panel_message_id=None,
        )
        self.store.add_room(room)
        try:
            await discord_call(lambda: member.move_to(channel))
        except discord.HTTPException as e:
            log.warning("could not move %s into new room: %s", member.id, e)
            if isinstance(e, discord.Forbidden):
                await self.bot.report_error(e, "voice_rooms.move_member")
            self.store.delete_room(room.id)
            await self._discard(channel)
            return
        self.bot.dispatch("room_created", room)
        self.bot.dispatch("board_dirty", mode)

    async def _discard(self, channel: discord.VoiceChannel) -> None:
        try:
            await self.queue.run(lambda: discord_call(channel.delete))
        except discord.NotFound:
            pass

    async def _make_channel(
        self, guild: discord.Guild, mode: Mode
    ) -> discord.VoiceChannel | None:
        """Runs inside the serial queue: pick/create category, name and create."""
        cats = [guild.get_channel(cid) for cid in self._categories(mode)]
        cats = [c for c in cats if isinstance(c, discord.CategoryChannel)]
        if not cats:
            log.error("no usable category for mode %s", mode.value)
            return None
        names = [ch.name for c in cats for ch in c.channels]
        idx = pick_category(
            [len(c.channels) for c in cats], self.cfg.voice_category_max_channels
        )
        if idx is None:
            base = cats[0]
            category = await discord_call(
                lambda: guild.create_category(
                    overflow_category_name(base.name, len(cats)),
                    overwrites=base.overwrites,
                )
            )
            self.store.add_category(mode, category.id)
        else:
            category = cats[idx]
        name = next_room_name(self.cfg.modes[mode].name_template, names)
        return await discord_call(
            lambda: guild.create_voice_channel(
                name,
                category=category,
                overwrites=category.overwrites,
                user_limit=self.cfg.voice_default_user_limit,
            )
        )

    # -- reconcile (startup and every reconnect) ---------------------------
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # on_ready fires again after a gateway re-identify; voice events missed
        # meanwhile can leave empty rooms without a delete timer, so reconcile
        # every time. Runs are serialized; each run is idempotent (adopted rooms
        # are tracked afterwards, timers are cancel-then-start).
        async with self._reconcile_lock:
            try:
                await self._reconcile_all()
            except Exception as e:
                await self.bot.report_error(e, "voice_rooms.reconcile")

    async def _reconcile_all(self) -> None:
        guild = self.bot.get_guild(self.cfg.guild_id)
        if guild is None:
            log.error("guild %s not found; skipping reconcile", self.cfg.guild_id)
            return
        self._seed_categories()
        for mode in self._modes():
            all_entrances = {
                mc.entrance_channel_id for mc in self.cfg.modes.values()
            }
            tracked_elsewhere = {
                r.id for r in self.store.list_rooms() if r.mode != mode
            }
            live: dict[int, discord.VoiceChannel] = {}
            for cid in self._categories(mode):
                cat = guild.get_channel(cid)
                if not isinstance(cat, discord.CategoryChannel):
                    continue
                for vc in cat.voice_channels:
                    live[vc.id] = vc
            counts = exclude_unmanaged(
                {i: len(v.members) for i, v in live.items()},
                all_entrances,
                tracked_elsewhere,
            )
            live = {i: v for i, v in live.items() if i in counts}
            tracked = {r.id: r for r in self.store.list_rooms(mode)}
            result = reconcile(
                tracked.keys(), {i: len(v.members) for i, v in live.items()}
            )
            # A tracked room moved out of the managed categories (e.g. by an
            # admin) is still a live temporary room: keep tracking it so it is
            # deleted when empty instead of being orphaned.
            gone, moved = partition_stale(
                result.stale,
                lambda rid: isinstance(guild.get_channel(rid), discord.VoiceChannel),
            )
            for rid in gone:
                self.store.delete_room(rid)
                self.store.delete_entry_by_room(rid)
            for rid in moved:
                vc = guild.get_channel(rid)
                if not vc.members:
                    self._on_room_empty(tracked[rid])
            for rid in result.adopt:
                vc = live[rid]
                self.store.add_room(
                    Room(
                        id=rid,
                        mode=mode,
                        owner_id=vc.members[0].id,
                        category_id=vc.category_id or 0,
                        created_at=time.time(),
                        locked=False,
                        panel_message_id=None,
                    )
                )
            for rid in result.remove:
                try:
                    await self.queue.run(lambda vc=live[rid]: discord_call(vc.delete))
                except discord.NotFound:
                    pass
                except Exception as e:
                    await self.bot.report_error(e, "voice_rooms.reconcile_remove")
            for rid, room in tracked.items():
                if rid in live and not live[rid].members:
                    self._on_room_empty(room)
        if self.cfg.board_remove_when_room_empty:
            # Non-temp channels emptied while disconnected lose their entry too.
            tracked_ids = {r.id for r in self.store.list_rooms()}
            for mode in self._modes():
                for entry in self.store.list_entries(mode):
                    vc = guild.get_channel(entry.room_id)
                    if (
                        entry.room_id not in tracked_ids
                        and isinstance(vc, discord.VoiceChannel)
                        and not vc.members
                    ):
                        self.store.delete_entry_by_room(entry.room_id)
        for mode in self._modes():
            self.bot.dispatch("board_dirty", mode)


async def setup(bot) -> None:
    await bot.add_cog(VoiceRooms(bot))
