"""Admin slash commands: editable ad, footer and delete-original settings."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..settings_view import KEY_AD, KEY_DELETE, KEY_FOOTER, parse_on_off

log = logging.getLogger(__name__)

FOOTER_LIMIT = 2048  # Discord embed footer text limit
AD_LIMIT = 1024  # keep the ad within an embed field value
CLEAR_WORD = "clear"

MSG_NO_PERM = "需要「管理服务器」权限"
MSG_ERROR = "操作失败，请稍后再试"


def _too_long(label: str, limit: int) -> str:
    return f"{label}太长了，最多 {limit} 个字符"


async def _reply(interaction: discord.Interaction, content: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True)
    else:
        await interaction.response.send_message(content, ephemeral=True)


class Admin(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.store = bot.store

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await _reply(interaction, MSG_NO_PERM)
            return
        cmd = interaction.command.qualified_name if interaction.command else "?"
        await self.bot.report_error(getattr(error, "original", error), f"command {cmd}")
        try:
            await _reply(interaction, MSG_ERROR)
        except discord.HTTPException:
            pass

    def _set_text(self, key: str, text: str, label: str, limit: int) -> str:
        """Store the text (or clear); returns the confirmation/error message."""
        if text.strip().lower() == CLEAR_WORD:
            self.store.set_setting(key, "")
            return f"已清空{label}"
        value = text.strip()
        if len(value) > limit:
            return _too_long(label, limit)
        self.store.set_setting(key, value)
        return f"{label}已设为：{value}"

    @app_commands.command(name="motto", description="设置卡片页脚文案（填 clear 清空）")
    @app_commands.describe(文字="页脚文字，clear 表示清空")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def motto(self, interaction: discord.Interaction, 文字: str) -> None:
        await _reply(interaction, self._set_text(KEY_FOOTER, 文字, "页脚", FOOTER_LIMIT))

    @app_commands.command(name="ad", description="设置卡片广告位文案（填 clear 清空）")
    @app_commands.describe(文字="广告文字，clear 表示清空")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ad(self, interaction: discord.Interaction, 文字: str) -> None:
        await _reply(interaction, self._set_text(KEY_AD, 文字, "广告位", AD_LIMIT))

    setting = app_commands.Group(
        name="setting",
        description="卡片设置",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @setting.command(
        name="delete_original", description="发卡片后是否删除原消息"
    )
    @app_commands.describe(开关="on 或 off", 频道="只对该频道生效；不填则全局")
    @app_commands.choices(
        开关=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
        ]
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_original(
        self,
        interaction: discord.Interaction,
        开关: app_commands.Choice[str],
        频道: discord.TextChannel | None = None,
    ) -> None:
        try:
            value = "on" if parse_on_off(开关.value) else "off"
        except ValueError:
            await _reply(interaction, "开关只能是 on 或 off")
            return
        if 频道 is None:
            self.store.set_setting(KEY_DELETE, value)
            await _reply(interaction, f"删除原消息（全局）已设为 {value}")
        else:
            self.store.set_setting(f"{KEY_DELETE}.{频道.id}", value)
            await _reply(interaction, f"删除原消息（{频道.mention}）已设为 {value}")


async def setup(bot) -> None:
    await bot.add_cog(Admin(bot))
