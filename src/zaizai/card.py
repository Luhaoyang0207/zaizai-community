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
) -> discord.Embed:
    title = text.strip() or DEFAULT_TITLE
    if len(title) > TITLE_LIMIT:
        title = title[: TITLE_LIMIT - 1] + "…"
    lines = [
        f"找人组队看这里 <#{board_channel_id}>",
        f"发起人 <@{host_id}> · <t:{int(now)}:R>",
    ]
    if ad_text:
        lines.append(ad_text)
    embed = discord.Embed(title=title, description="\n".join(lines))
    if footer_text:
        embed.set_footer(text=footer_text)
    return embed
