"""Room control panel: lock/unlock and "team full" buttons, plus /panel recall."""

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import discord_call
from ..models import Room

log = logging.getLogger(__name__)

ACTIONS = ("lock", "full")
PANEL_TEMPLATE = r"zaizai:panel:(?P<action>lock|full):(?P<room>\d+)"
_PANEL_RE = re.compile(PANEL_TEMPLATE)

FULL_LABEL = "组队已满"
MSG_NOT_OWNER = "只有房主可以使用面板"
MSG_NO_ROOM = "房间已不存在"
MSG_NO_ENTRY = "当前没有组队信息"
MSG_ENTRY_REMOVED = "已移除组队信息"
MSG_LOCKED = "房间已锁，其他人不能再加入"
MSG_UNLOCKED = "房间已开，其他人可以加入"
MSG_FORBIDDEN = "机器人缺少权限，操作失败"
MSG_ERROR = "操作失败，请稍后再试"
MSG_ONLY_ROOM_CHAT = "只能在临时房间的聊天里使用"
MSG_NOT_IN_ROOM = "你需要在这个语音房间里才能召唤面板"
MSG_DISABLED = "面板功能已关闭"
MSG_RECALLED = "已重新发送面板"


# -- pure helpers ----------------------------------------------------------
def panel_custom_id(action: str, room_id: int) -> str:
    if action not in ACTIONS:
        raise ValueError(f"unknown panel action: {action!r}")
    return f"zaizai:panel:{action}:{room_id}"


def parse_panel_custom_id(custom_id: str) -> tuple[str, int] | None:
    m = _PANEL_RE.fullmatch(custom_id)
    if m is None:
        return None
    return m["action"], int(m["room"])


def lock_label(locked: bool) -> str:
    return "🔒锁" if locked else "🔓开"


def owner_denial(room: Room | None, user_id: int) -> str | None:
    """Reason a user may not press a panel button, or None if allowed."""
    if room is None:
        return MSG_NO_ROOM
    if room.owner_id != user_id:
        return MSG_NOT_OWNER
    return None


# -- persistent buttons ----------------------------------------------------
class PanelButton(discord.ui.DynamicItem[discord.ui.Button], template=PANEL_TEMPLATE):
    """Panel button whose custom_id carries action and room id (survives restarts)."""

    def __init__(self, action: str, room_id: int, locked: bool = False) -> None:
        if action == "lock":
            label, style = lock_label(locked), discord.ButtonStyle.secondary
        else:
            label, style = FULL_LABEL, discord.ButtonStyle.primary
        super().__init__(
            discord.ui.Button(
                label=label, style=style, custom_id=panel_custom_id(action, room_id)
            )
        )
        self.action = action
        self.room_id = room_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match[str], /):
        return cls(match["action"], int(match["room"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("Panel")
        if cog is None:
            await _reply(interaction, MSG_ERROR)
            return
        await cog.handle_button(interaction, self.action, self.room_id)


async def _reply(interaction: discord.Interaction, text: str) -> None:
    """Ephemeral reply that works whether or not the interaction was answered."""
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class Panel(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.cfg = bot.cfg
        self.store = bot.store

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(PanelButton)

    async def cog_unload(self) -> None:
        self.bot.remove_dynamic_items(PanelButton)

    # -- panel message ---------------------------------------------------
    def build_view(self, room: Room) -> discord.ui.View | None:
        view = discord.ui.View(timeout=None)
        if self.cfg.panel_button_lock:
            view.add_item(PanelButton("lock", room.id, room.locked))
        if self.cfg.panel_button_full:
            view.add_item(PanelButton("full", room.id))
        return view if view.children else None

    async def post_panel(self, channel: discord.abc.Messageable, room: Room) -> None:
        kwargs = {}
        view = self.build_view(room)
        if view is not None:
            kwargs["view"] = view
        message = await discord_call(
            lambda: channel.send(
                f"<@{room.owner_id}>\n{self.cfg.panel_help_text}",
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=[discord.Object(id=room.owner_id)],
                    replied_user=False,
                ),
                **kwargs,
            )
        )
        self.store.set_panel_message(room.id, message.id)

    @commands.Cog.listener()
    async def on_room_created(self, room: Room) -> None:
        if not self.cfg.panel_enabled:
            return
        try:
            channel = self.bot.get_channel(room.id)
            if channel is None:
                return
            await self.post_panel(channel, room)
        except Exception as e:
            await self.bot.report_error(e, "panel.post")

    # -- buttons ---------------------------------------------------------
    async def handle_button(
        self, interaction: discord.Interaction, action: str, room_id: int
    ) -> None:
        try:
            room = self.store.get_room(room_id)
            denial = owner_denial(room, interaction.user.id)
            if denial is not None:
                await _reply(interaction, denial)
                return
            if action == "lock":
                await self._toggle_lock(interaction, room)
            else:
                await self._mark_full(interaction, room)
        except Exception as e:
            try:
                await _reply(
                    interaction,
                    MSG_FORBIDDEN if isinstance(e, discord.Forbidden) else MSG_ERROR,
                )
            except Exception:
                log.exception("could not answer panel interaction")
            await self.bot.report_error(e, f"panel.{action}")

    async def _toggle_lock(self, interaction: discord.Interaction, room: Room) -> None:
        guild = interaction.guild
        channel = guild.get_channel(room.id) if guild is not None else None
        if channel is None:
            await _reply(interaction, MSG_NO_ROOM)
            return
        await interaction.response.defer()
        locked = not room.locked
        if locked:
            # Owner keeps connect so they can rejoin; then deny @everyone.
            await self._set_connect(channel, interaction.user, True)
            await self._set_connect(channel, guild.default_role, False)
        else:
            await self._set_connect(channel, guild.default_role, None)
        self.store.set_locked(room.id, locked)
        room = self.store.get_room(room.id) or room
        view = self.build_view(room)
        if view is not None:
            await interaction.edit_original_response(view=view)
        await interaction.followup.send(
            MSG_LOCKED if locked else MSG_UNLOCKED, ephemeral=True
        )

    @staticmethod
    async def _set_connect(channel, target, value: bool | None) -> None:
        """Change only the connect bit of target's overwrite, keeping the rest."""
        overwrite = channel.overwrites_for(target)
        overwrite.connect = value
        new = None if overwrite.is_empty() else overwrite
        await discord_call(lambda: channel.set_permissions(target, overwrite=new))

    async def _mark_full(self, interaction: discord.Interaction, room: Room) -> None:
        if self.store.delete_entry_by_room(room.id):
            self.bot.dispatch("board_dirty", room.mode)
            await _reply(interaction, MSG_ENTRY_REMOVED)
        else:
            await _reply(interaction, MSG_NO_ENTRY)

    # -- /panel ----------------------------------------------------------
    @app_commands.command(name="panel", description="重新召唤本房间的控制面板")
    @app_commands.guild_only()
    async def panel_command(self, interaction: discord.Interaction) -> None:
        try:
            await self._recall(interaction)
        except Exception as e:
            try:
                await _reply(interaction, MSG_ERROR)
            except Exception:
                log.exception("could not answer /panel")
            await self.bot.report_error(e, "panel.recall")

    async def _recall(self, interaction: discord.Interaction) -> None:
        if not self.cfg.panel_enabled:
            await _reply(interaction, MSG_DISABLED)
            return
        channel = interaction.channel
        room = self.store.get_room(channel.id) if channel is not None else None
        if room is None:
            await _reply(interaction, MSG_ONLY_ROOM_CHAT)
            return
        voice = getattr(interaction.user, "voice", None)
        if voice is None or voice.channel is None or voice.channel.id != room.id:
            await _reply(interaction, MSG_NOT_IN_ROOM)
            return
        await interaction.response.defer(ephemeral=True)
        old_id = room.panel_message_id
        await self.post_panel(channel, room)
        if old_id is not None:
            try:
                await channel.get_partial_message(old_id).delete()
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                log.warning("could not delete old panel %s: %s", old_id, e)
        await _reply(interaction, MSG_RECALLED)


async def setup(bot) -> None:
    await bot.add_cog(Panel(bot))
