"""LFG command handling: parse the command, reply with a card, record the entry."""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from ..bot import discord_call
from ..card import build_card
from ..commands import LfgDecision, allowed_modes, decide_lfg, parse_lfg_command
from ..config import mode_in_scope
from ..models import Mode
from ..settings_view import KEY_AD, KEY_DELETE, KEY_FOOTER, effective_setting

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

    def _allowed_modes(self, channel) -> set[Mode]:
        team = {
            mc.lfg_channel_id: m
            for m, mc in self.cfg.modes.items()
            if mode_in_scope(self.cfg, m) and mc.lfg_channel_id != 0
        }
        return allowed_modes(
            channel.id,
            isinstance(channel, discord.VoiceChannel),
            team,
            self._commands().values(),
            self.cfg.commands_allow_in_room_chat,
        )

    def _author_voice(self, author, guild: discord.Guild):
        """The author's current voice channel in this guild, or None.

        Entrance channels do not count: an entry there would point players at
        the join-to-create lobby, not at the author's team.
        """
        voice = getattr(author, "voice", None)
        channel = getattr(voice, "channel", None)
        if not isinstance(channel, discord.VoiceChannel) or channel.guild.id != guild.id:
            return None
        entrances = {mc.entrance_channel_id for mc in self.cfg.modes.values()}
        if channel.id in entrances:
            return None
        return channel

    def _card_settings(self, channel_id: int) -> tuple[str | None, str | None]:
        """(ad_text, footer_text) in effect now; ad_enabled=false hides the ad."""
        ad = None
        if self.cfg.card_ad_enabled:
            ad = effective_setting(self.store, self.cfg, KEY_AD)
        footer = effective_setting(self.store, self.cfg, KEY_FOOTER)
        return (ad or None, footer or None)

    def _delete_original(self, channel_id: int) -> bool:
        return bool(
            effective_setting(self.store, self.cfg, KEY_DELETE, channel_id)
        )

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
        voice = self._author_voice(message.author, message.guild)
        decision = decide_lfg(
            parsed, self._allowed_modes(message.channel), voice is not None
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
        assert voice is not None

        now = time.time()
        ad_text, footer_text = self._card_settings(message.channel.id)
        embed = build_card(
            parsed.text,
            message.author.id,
            self.cfg.board_channel_id,
            now,
            ad_text,
            footer_text,
            show_requirement=self.cfg.card_show_requirement,
            show_board_link=self.cfg.card_show_board_link,
            show_host=self.cfg.card_show_host,
        )
        reply = await discord_call(
            lambda: message.reply(embed=embed, mention_author=False)
        )
        previous = self.store.get_entry_by_room(voice.id)
        self.store.upsert_entry(
            voice.id,
            parsed.mode,
            parsed.text,
            message.author.id,
            card_channel_id=reply.channel.id,
            card_message_id=reply.id,
            now=now,
        )
        self.bot.dispatch("board_dirty", parsed.mode)
        if previous is not None and previous.mode != parsed.mode:
            # The channel's entry moved to the other board (one entry per room).
            self.bot.dispatch("board_dirty", previous.mode)

        if self._delete_original(message.channel.id):
            try:
                await discord_call(message.delete)
            except discord.NotFound:
                pass
            except discord.Forbidden as e:
                await self.bot.report_error(e, "lfg.delete_original")


async def setup(bot) -> None:
    await bot.add_cog(Lfg(bot))
