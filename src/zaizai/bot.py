"""Bot skeleton: config-driven cog loading and shared error handling."""

from __future__ import annotations

import logging
import sys
from collections.abc import Awaitable, Callable
from typing import TypeVar

import discord
from discord import app_commands
from discord.ext import commands

from .asyncutil import with_retry
from .config import Config
from .store import Store

log = logging.getLogger(__name__)

T = TypeVar("T")

VALID_COGS = ("voice_rooms", "lfg", "board", "panel", "admin")


def enabled_cogs(cfg: Config) -> list[str]:
    """Cog module names from config; unknown names raise ValueError."""
    names = list(cfg.modules_enabled)
    unknown = [n for n in names if n not in VALID_COGS]
    if unknown:
        raise ValueError(f"unknown module(s) in modules.enabled: {unknown}")
    return names


def cog_handles_app_errors(command) -> bool:
    """True if the command's cog has its own cog_app_command_error.

    discord.py calls that handler *and* tree.on_error, so the tree-level
    handler must skip such errors to avoid double reports.
    """
    binding = getattr(command, "binding", None)
    return getattr(binding, "__discord_app_commands_error_handler__", None) is not None


class ErrorNotifier:
    """Remembers which error kinds were already reported to the board channel."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def should_notify(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


async def discord_call(
    factory: Callable[[], Awaitable[T]], delay_sec: float = 1.0
) -> T:
    """Run a Discord API call, retrying transient HTTPExceptions up to 3 times.

    Forbidden and NotFound are permanent and re-raised immediately.
    """

    async def attempt() -> T:
        try:
            return await factory()
        except (discord.Forbidden, discord.NotFound) as e:
            raise _Permanent(e) from e

    try:
        return await with_retry(
            attempt, attempts=3, delay_sec=delay_sec, retry_on=(discord.HTTPException,)
        )
    except _Permanent as p:
        raise p.original from None


class _Permanent(Exception):
    """Wraps a non-retryable error so with_retry lets it through."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


class ZaizaiBot(commands.Bot):
    def __init__(self, cfg: Config, store: Store) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.cfg = cfg
        self.store = store
        self.notifier = ErrorNotifier()
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        for name in enabled_cogs(self.cfg):
            await self.load_extension(f"zaizai.cogs.{name}")
        if self.cfg.guild_id:
            guild = discord.Object(id=self.cfg.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def close(self) -> None:
        await super().close()
        self.store.close()

    async def report_error(self, exc: BaseException, where: str) -> None:
        """Log the error; for missing permissions notify the board channel once."""
        if isinstance(exc, discord.Forbidden):
            log.error("missing permission in %s: %s", where, exc)
            key = f"forbidden:{where}"
            if self.notifier.should_notify(key):
                await self._notify_board(
                    f"zaizai is missing a permission ({where}): {exc.text or exc}. "
                    "Please check the bot's role permissions."
                )
        else:
            log.error("unhandled error in %s", where, exc_info=exc)

    async def _notify_board(self, text: str) -> None:
        try:
            channel = self.get_channel(self.cfg.board_channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.cfg.board_channel_id)
            await channel.send(text)
        except Exception:
            log.exception("could not post permission notice to board channel")

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        exc = sys.exc_info()[1]
        if exc is None:
            return
        await self.report_error(exc, f"event {event_method}")

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        cmd = interaction.command.qualified_name if interaction.command else "?"
        if isinstance(error, app_commands.CheckFailure):
            log.warning("check failed for command %s: %s", cmd, error)
            return
        if cog_handles_app_errors(interaction.command):
            return  # already reported by the cog's cog_app_command_error
        cause = getattr(error, "original", error)
        await self.report_error(cause, f"command {cmd}")
