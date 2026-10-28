import re
from collections.abc import Mapping
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


def decide_lfg(
    parsed: ParsedCommand | None,
    channel_mode: Mode | None,
    author_room_mode: Mode | None,
) -> LfgDecision:
    if parsed is None or parsed.mode != channel_mode:
        return LfgDecision.IGNORE
    if author_room_mode != parsed.mode:
        return LfgDecision.NEED_VOICE
    return LfgDecision.OK
