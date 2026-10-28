"""The LFG card embed posted under a player's command message."""

from __future__ import annotations

import discord

DEFAULT_TITLE = "组队中"
TITLE_LIMIT = 256  # Discord embed title limit


def build_card(
    text: str,
    host_id: int,
    board_channel_id: int,
    now: float,
    ad_text: str | None,
    footer_text: str | None,
    *,
    show_requirement: bool = True,
    show_board_link: bool = True,
    show_host: bool = True,
) -> discord.Embed:
    title = (text.strip() if show_requirement else "") or DEFAULT_TITLE
    if len(title) > TITLE_LIMIT:
        title = title[: TITLE_LIMIT - 1] + "…"
    lines = []
    if show_board_link:
        lines.append(f"找人组队看这里 <#{board_channel_id}>")
    if show_host:
        lines.append(f"发起人 <@{host_id}> · <t:{int(now)}:R>")
    if ad_text:
        lines.append(ad_text)
    embed = discord.Embed(title=title, description="\n".join(lines) or None)
    if footer_text:
        embed.set_footer(text=footer_text)
    return embed
