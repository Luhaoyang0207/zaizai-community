"""Runtime-editable card settings: Store overrides on top of config defaults."""

from __future__ import annotations

from .config import Config
from .store import Store

KEY_AD = "card.ad_text"
KEY_FOOTER = "card.footer_text"
KEY_DELETE = "card.delete_original"

_TRUE = {"on", "true"}
_FALSE = {"off", "false"}


def parse_on_off(raw: str) -> bool:
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"expected on/off, got {raw!r}")


def effective_setting(
    store: Store, cfg: Config, key: str, channel_id: int | None = None
) -> str | bool | None:
    """Stored override if any, else the config default.

    Text keys: a stored "" means cleared (None). card.delete_original: the
    per-channel override beats the global one, which beats the config.
    """
    if key == KEY_AD or key == KEY_FOOTER:
        stored = store.get_setting(key)
        if stored is None:
            default = cfg.card_ad_text if key == KEY_AD else cfg.card_footer_text
            return default or None
        return stored or None
    if key == KEY_DELETE:
        if channel_id is not None:
            raw = store.get_setting(f"{KEY_DELETE}.{channel_id}")
            if raw is not None:
                return parse_on_off(raw)
        raw = store.get_setting(KEY_DELETE)
        if raw is not None:
            return parse_on_off(raw)
        return cfg.card_delete_original
    raise ValueError(f"unknown setting: {key!r}")
