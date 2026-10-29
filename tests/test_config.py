import re

import pytest
import tomllib
from pathlib import Path

from zaizai.config import load_config, mode_in_scope
from zaizai.models import Mode

ROOT = Path(__file__).resolve().parent.parent
# The committed template holds the defaults; the real settings.toml is the
# owner's local copy and may differ in values (never in keys).
TEMPLATE = ROOT / "config" / "settings.dev.toml.example"
SETTINGS = ROOT / "config" / "settings.toml"
SOURCES = [
    pytest.param(TEMPLATE, id="template"),
    pytest.param(
        SETTINGS,
        id="settings",
        marks=pytest.mark.skipif(not SETTINGS.exists(), reason="no local settings.toml"),
    ),
]
PARAMETERS = ROOT / "docs" / "PARAMETERS.md"

KEY_ROW = re.compile(r"^\|\s*`([a-z0-9_.]+)`\s*\|", re.MULTILINE)


def _lookup(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, f"missing {dotted}"
        node = node[part]
    return node


@pytest.mark.parametrize("source", SOURCES)
def test_every_parameters_key_exists_in_settings_toml(source):
    keys = KEY_ROW.findall(PARAMETERS.read_text(encoding="utf-8"))
    assert len(keys) > 30
    data = tomllib.loads(source.read_text(encoding="utf-8"))
    for key in keys:
        _lookup(data, key)


def test_load_config_values():
    cfg = load_config(TEMPLATE)
    assert cfg.board_entry_timeout_min == 30
    assert cfg.board_refresh_debounce_sec == 5
    assert cfg.voice_category_max_channels == 45
    assert cfg.voice_reuse_empty_rooms is False
    assert cfg.card_after_entry_end == "keep"
    assert cfg.modes[Mode.RANKED].command == "pw"
    assert cfg.modes[Mode.UNRATED].command == "pp"
    assert cfg.voice_name_template[Mode.RANKED] == "排位房 {n}"
    assert cfg.modes[Mode.UNRATED].name_template == "匹配房 {n}"
    assert cfg.modules_enabled == ("voice_rooms", "lfg", "board", "panel", "admin")


def test_mode_in_scope():
    cfg = load_config(TEMPLATE)
    assert mode_in_scope(cfg, Mode.RANKED)
    from dataclasses import replace

    narrow = replace(cfg, modules_mode_scope=(Mode.UNRATED,))
    assert mode_in_scope(narrow, Mode.UNRATED)
    assert not mode_in_scope(narrow, Mode.RANKED)


def _write_variant(source: Path, tmp_path, old: str, new: str) -> Path:
    text = source.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "settings.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize(
    "old, new, key",
    [
        ('after_entry_end = "keep"', 'after_entry_end = "delete"', "card.after_entry_end"),
        ("reuse_empty_rooms = false", "reuse_empty_rooms = true", "voice.reuse_empty_rooms"),
        ('owner_permissions = "lock_only"', 'owner_permissions = "all"', "panel.owner_permissions"),
        ("button_refresh = false", "button_refresh = true", "panel.button_refresh"),
        ("button_crosshair = false", "button_crosshair = true", "panel.button_crosshair"),
    ],
)
def test_load_config_rejects_unimplemented_values(source, tmp_path, old, new, key):
    with pytest.raises(ValueError, match=re.escape(key)):
        load_config(_write_variant(source, tmp_path, old, new))


def _with_other_categories(source: Path, tmp_path, line: str) -> Path:
    text = source.read_text(encoding="utf-8")
    new, n = re.subn(
        r"(\[modes\.other\]\n(?:[^\[\n].*\n)*?)category_ids = .*\n",
        lambda m: m.group(1) + line + "\n",
        text,
    )
    assert n == 1
    path = tmp_path / "settings.toml"
    path.write_text(new, encoding="utf-8")
    return path


@pytest.mark.parametrize("source", SOURCES)
def test_category_ids_list_keeps_order_and_drops_zero(source, tmp_path):
    cfg = load_config(_with_other_categories(source, tmp_path, "category_ids = [30, 0, 10, 20]"))
    assert cfg.modes[Mode.OTHER].category_ids == (30, 10, 20)


@pytest.mark.parametrize("source", SOURCES)
def test_old_single_category_id_still_works(source, tmp_path):
    cfg = load_config(_with_other_categories(source, tmp_path, "category_id = 42"))
    assert cfg.modes[Mode.OTHER].category_ids == (42,)


@pytest.mark.parametrize("source", SOURCES)
def test_old_single_category_id_zero_means_none(source, tmp_path):
    cfg = load_config(_with_other_categories(source, tmp_path, "category_id = 0"))
    assert cfg.modes[Mode.OTHER].category_ids == ()


@pytest.mark.parametrize("source", SOURCES)
def test_empty_command_means_disabled(source, tmp_path):
    text = source.read_text(encoding="utf-8")
    new, n = re.subn(r'(?m)^other = "[^"{]*"$', 'other = ""', text, count=1)
    assert n == 1
    path = tmp_path / "settings.toml"
    path.write_text(new, encoding="utf-8")
    assert load_config(path).modes[Mode.OTHER].command is None
