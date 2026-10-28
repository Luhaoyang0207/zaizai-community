"""Load config/settings.toml into a frozen Config.

One attribute per docs/PARAMETERS.md key (dots become underscores).
`voice_name_template` is a dict[Mode, str]. `modules_mode_scope` is a
tuple[Mode, ...]. Channel IDs live in `guild_id`, `board_channel_id` and
`modes[mode]`.
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import Mode


@dataclass(frozen=True)
class ModeConfig:
    mode: Mode
    command: str | None  # None = disabled
    entrance_channel_id: int
    lfg_channel_id: int
    category_id: int
    name_template: str


@dataclass(frozen=True)
class Config:
    guild_id: int
    board_channel_id: int
    modes: dict[Mode, ModeConfig]

    commands_accept_fullwidth: bool
    commands_need_voice: bool
    commands_need_voice_msg: str
    commands_allow_in_room_chat: bool

    card_delete_original: bool
    card_after_entry_end: str
    card_show_requirement: bool
    card_show_board_link: bool
    card_show_host: bool
    card_ad_enabled: bool
    card_ad_text: str
    card_footer_text: str

    board_entry_timeout_min: int
    board_remove_when_room_empty: bool
    board_refresh_debounce_sec: int
    board_max_entries_per_message: int
    board_empty_text: str
    board_show_member_count: bool

    voice_name_template: dict[Mode, str]
    voice_default_user_limit: int
    voice_empty_delete_delay_sec: int
    voice_reuse_empty_rooms: bool
    voice_category_max_channels: int
    voice_create_queue_interval_ms: int

    panel_enabled: bool
    panel_owner_permissions: str
    panel_button_lock: bool
    panel_button_full: bool
    panel_button_refresh: bool
    panel_button_crosshair: bool
    panel_recall_command: str
    panel_help_text: str

    modules_enabled: tuple[str, ...]
    modules_mode_scope: tuple[Mode, ...]


# Keys whose other values the first version does not implement (fixed in v1).
FIXED_VALUES: dict[str, object] = {
    "card.after_entry_end": "keep",
    "voice.reuse_empty_rooms": False,
    "panel.owner_permissions": "lock_only",
    "panel.button_refresh": False,
    "panel.button_crosshair": False,
}


def _check_fixed(d: dict) -> None:
    for key, expected in FIXED_VALUES.items():
        section, name = key.split(".")
        value = d[section][name]
        if value != expected:
            raise ValueError(
                f"{key} = {value!r} is not supported in this version; "
                f"only {expected!r} is implemented (see docs/PARAMETERS.md)"
            )


def load_config(path: str | Path) -> Config:
    with open(path, "rb") as f:
        d = tomllib.load(f)
    _check_fixed(d)

    guild, commands, card = d["guild"], d["commands"], d["card"]
    board, voice, panel, modules = d["board"], d["voice"], d["panel"], d["modules"]

    modes = {}
    for mode in Mode:
        m = d["modes"][mode.value]
        modes[mode] = ModeConfig(
            mode=mode,
            command=commands[mode.value] or None,
            entrance_channel_id=m["entrance_channel_id"],
            lfg_channel_id=m["lfg_channel_id"],
            category_id=m["category_id"],
            name_template=voice["name_template"][mode.value],
        )

    return Config(
        guild_id=guild["id"],
        board_channel_id=guild["board_channel_id"],
        modes=modes,
        commands_accept_fullwidth=commands["accept_fullwidth"],
        commands_need_voice=commands["need_voice"],
        commands_need_voice_msg=commands["need_voice_msg"],
        commands_allow_in_room_chat=commands["allow_in_room_chat"],
        card_delete_original=card["delete_original"],
        card_after_entry_end=card["after_entry_end"],
        card_show_requirement=card["show_requirement"],
        card_show_board_link=card["show_board_link"],
        card_show_host=card["show_host"],
        card_ad_enabled=card["ad_enabled"],
        card_ad_text=card["ad_text"],
        card_footer_text=card["footer_text"],
        board_entry_timeout_min=board["entry_timeout_min"],
        board_remove_when_room_empty=board["remove_when_room_empty"],
        board_refresh_debounce_sec=board["refresh_debounce_sec"],
        board_max_entries_per_message=board["max_entries_per_message"],
        board_empty_text=board["empty_text"],
        board_show_member_count=board["show_member_count"],
        voice_name_template={m: voice["name_template"][m.value] for m in Mode},
        voice_default_user_limit=voice["default_user_limit"],
        voice_empty_delete_delay_sec=voice["empty_delete_delay_sec"],
        voice_reuse_empty_rooms=voice["reuse_empty_rooms"],
        voice_category_max_channels=voice["category_max_channels"],
        voice_create_queue_interval_ms=voice["create_queue_interval_ms"],
        panel_enabled=panel["enabled"],
        panel_owner_permissions=panel["owner_permissions"],
        panel_button_lock=panel["button_lock"],
        panel_button_full=panel["button_full"],
        panel_button_refresh=panel["button_refresh"],
        panel_button_crosshair=panel["button_crosshair"],
        panel_recall_command=panel["recall_command"],
        panel_help_text=panel["help_text"],
        modules_enabled=tuple(modules["enabled"]),
        modules_mode_scope=tuple(Mode(m) for m in modules["mode_scope"]),
    )


def mode_in_scope(cfg: Config, mode: Mode) -> bool:
    return mode in cfg.modules_mode_scope
