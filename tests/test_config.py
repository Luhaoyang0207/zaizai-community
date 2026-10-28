import re
import tomllib
from pathlib import Path

from zaizai.config import load_config, mode_in_scope
from zaizai.models import Mode

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.toml"
PARAMETERS = ROOT / "docs" / "PARAMETERS.md"

KEY_ROW = re.compile(r"^\|\s*`([a-z0-9_.]+)`\s*\|", re.MULTILINE)


def _lookup(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, f"missing {dotted}"
        node = node[part]
    return node


def test_every_parameters_key_exists_in_settings_toml():
    keys = KEY_ROW.findall(PARAMETERS.read_text(encoding="utf-8"))
    assert len(keys) > 30
    data = tomllib.loads(SETTINGS.read_text(encoding="utf-8"))
    for key in keys:
        _lookup(data, key)


def test_load_config_values():
    cfg = load_config(SETTINGS)
    assert cfg.board_entry_timeout_min == 30
    assert cfg.board_refresh_debounce_sec == 5
    assert cfg.voice_category_max_channels == 45
    assert cfg.voice_reuse_empty_rooms is False
    assert cfg.card_after_entry_end == "keep"
    assert cfg.modes[Mode.RANKED].command == "pw"
    assert cfg.modes[Mode.MATCH].command == "pp"
    assert cfg.modes[Mode.OTHER].command is None
    assert cfg.voice_name_template[Mode.RANKED] == "排位房 {n}"
    assert cfg.modes[Mode.MATCH].name_template == "匹配房 {n}"
    assert cfg.modules_enabled == ("voice_rooms", "lfg", "board", "panel", "admin")


def test_mode_in_scope():
    cfg = load_config(SETTINGS)
    assert mode_in_scope(cfg, Mode.RANKED)
    from dataclasses import replace

    narrow = replace(cfg, modules_mode_scope=(Mode.MATCH,))
    assert mode_in_scope(narrow, Mode.MATCH)
    assert not mode_in_scope(narrow, Mode.RANKED)
