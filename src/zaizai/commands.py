import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum

from zaizai.models import Mode


@dataclass(frozen=True)
class ParsedCommand:
    mode: Mode
    text: str


class LfgDecision(Enum):
    IGNORE = "ignore"
    NEED_VOICE = "need_voice"
    OK = "ok"


def parse_lfg_command(
    text: str, commands: Mapping[str, Mode], accept_fullwidth: bool = True
) -> ParsedCommand | None:
    if not commands:
        return None
    names = "|".join(re.escape(name) for name in commands)
    bang = "[!！]" if accept_fullwidth else "!"
    pattern = rf"^\s*{bang}\s*({names})(?=\s|$)\s*(.*)$"
    match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    lowered = {name.lower(): mode for name, mode in commands.items()}
    return ParsedCommand(lowered[match.group(1).lower()], match.group(2).strip())


def allowed_modes(
    channel_id: int,
    is_voice_chat: bool,
    team_channels: Mapping[int, Mode],
    command_modes: Collection[Mode],
    allow_in_voice_chat: bool,
) -> set[Mode]:
    """Modes whose command is accepted in this channel (D-014).

    A team text channel accepts only its own mode; the built-in chat of any
    voice channel accepts every enabled command (if allowed); others none.
    """
    if channel_id in team_channels:
        mode = team_channels[channel_id]
        return {mode} if mode in command_modes else set()
    if is_voice_chat and allow_in_voice_chat:
        return set(command_modes)
    return set()


def decide_lfg(
    parsed: ParsedCommand | None,
    allowed: Collection[Mode],
    author_in_voice: bool,
) -> LfgDecision:
    if parsed is None or parsed.mode not in allowed:
        return LfgDecision.IGNORE
    if not author_in_voice:
        return LfgDecision.NEED_VOICE
    return LfgDecision.OK
