"""LFG command handling: parse the command, reply with a card, record the entry."""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from ..bot import discord_call
from ..card import build_card
from ..commands import LfgDecision, decide_lfg, parse_lfg_command
from ..config import mode_in_scope
from ..models import Mode

log = logging.getLogger(__name__)


class Lfg(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.cfg = bot.cfg
        self.store = bot.store

    # -- helpers ---------------------------------------------------------
    def _commands(self) -> dict[str, Mode]:
        return {
            mc.command: m
            for m, mc in self.cfg.modes.items()
            if mode_in_scope(self.cfg, m) and mc.command
        }

    def _channel_mode(self, channel_id: int) -> Mode | None:
        for m, mc in self.cfg.modes.items():
            if (
                mode_in_scope(self.cfg, m)
                and mc.lfg_channel_id != 0
                and mc.lfg_channel_id == channel_id
            ):
                return m
        if self.cfg.commands_allow_in_room_chat:
            room = self.store.get_room(channel_id)
            if room is not None:
                return room.mode
        return None

    def _author_room(self, author):
        voice = getattr(author, "voice", None)
        channel = getattr(voice, "channel", None)
        if channel is None:
            return None
        return self.store.get_room(channel.id)

    def _card_settings(self, channel_id: int) -> tuple[str | None, str | None]:
        """(ad_text, footer_text); Task 14 switches this to effective_setting."""
        ad = self.cfg.card_ad_text if self.cfg.card_ad_enabled else None
        return (ad or None, self.cfg.card_footer_text or None)

    # -- events ----------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        try:
            await self._handle_message(message)
        except Exception as e:
            await self.bot.report_error(e, "lfg.on_message")

    async def _handle_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if self.cfg.guild_id and message.guild.id != self.cfg.guild_id:
            return
        parsed = parse_lfg_command(
            message.content,
            self._commands(),
            self.cfg.commands_accept_fullwidth,
        )
        if parsed is None:
            return
        room = self._author_room(message.author)
        decision = decide_lfg(
            parsed,
            self._channel_mode(message.channel.id),
            room.mode if room else None,
        )
        if decision is LfgDecision.IGNORE:
            return
        if decision is LfgDecision.NEED_VOICE:
            if self.cfg.commands_need_voice:
                await discord_call(
                    lambda: message.reply(
                        self.cfg.commands_need_voice_msg, mention_author=False
                    )
                )
            return
        assert room is not None

        now = time.time()
        ad_text, footer_text = self._card_settings(message.channel.id)
        embed = build_card(
            parsed.text,
            message.author.id,
            self.cfg.board_channel_id,
            now,
            ad_text,
            footer_text,
        )
        reply = await discord_call(
            lambda: message.reply(embed=embed, mention_author=False)
        )
        self.store.upsert_entry(
            room.id,
            parsed.mode,
            parsed.text,
            message.author.id,
            card_channel_id=reply.channel.id,
            card_message_id=reply.id,
            now=now,
        )
        self.bot.dispatch("board_dirty", parsed.mode)

        if self.cfg.card_delete_original:
            try:
                await discord_call(message.delete)
            except discord.NotFound:
                pass
            except discord.Forbidden as e:
                await self.bot.report_error(e, "lfg.delete_original")


async def setup(bot) -> None:
    await bot.add_cog(Lfg(bot))
