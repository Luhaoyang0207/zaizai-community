"""Join-to-create temporary voice rooms."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Collection, Mapping
from dataclasses import dataclass

import discord
from discord.ext import commands

from ..asyncutil import SerialQueue
from ..bot import discord_call
from ..config import mode_in_scope
from ..models import Mode, Room
from ..placement import next_room_name, pick_category
from ..reconcile import reconcile

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


class VoiceRooms(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.cfg = bot.cfg
        self.store = bot.store
        self.queue = SerialQueue(self.cfg.voice_create_queue_interval_ms)
        self._timers: dict[int, asyncio.Task[None]] = {}
        self._reconciled = False

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
        for m in self._modes():
            cat = self.cfg.modes[m].category_id
            if cat != 0 and not self.store.list_categories(m):
                self.store.add_category(m, cat)

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

        if t.left_room is not None:
            room = rooms[t.left_room]
            self.bot.dispatch("board_dirty", room.mode)
            if before.channel is not None and not before.channel.members:
                self._on_room_empty(room)
        if t.joined_room is not None:
            self._cancel_timer(t.joined_room)
            self.bot.dispatch("board_dirty", rooms[t.joined_room].mode)
        if t.entrance_joined is not None:
            await self._create_room(member, entrances[t.entrance_joined])

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
        cats = [guild.get_channel(cid) for cid in self.store.list_categories(mode)]
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

    # -- startup reconcile -----------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._reconciled:
            return
        self._reconciled = True
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
            for cid in self.store.list_categories(mode):
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
            for rid in result.stale:
                self.store.delete_room(rid)
                self.store.delete_entry_by_room(rid)
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
        for mode in self._modes():
            self.bot.dispatch("board_dirty", mode)


async def setup(bot) -> None:
    await bot.add_cog(VoiceRooms(bot))
