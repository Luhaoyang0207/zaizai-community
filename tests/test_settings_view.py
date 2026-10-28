import dataclasses

import pytest

from zaizai.config import load_config
from zaizai.settings_view import effective_setting, parse_on_off
from zaizai.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init()
    yield s
    s.close()


@pytest.fixture
def cfg():
    c = load_config("config/settings.toml")
    return dataclasses.replace(
        c, card_ad_text="cfg ad", card_footer_text="cfg foot", card_delete_original=False
    )


def test_falls_back_to_config_default(store, cfg):
    assert effective_setting(store, cfg, "card.ad_text") == "cfg ad"
    assert effective_setting(store, cfg, "card.footer_text") == "cfg foot"
    assert effective_setting(store, cfg, "card.delete_original", 5) is False


def test_empty_config_default_is_none(store, cfg):
    cfg = dataclasses.replace(cfg, card_ad_text="")
    assert effective_setting(store, cfg, "card.ad_text") is None


def test_store_override_wins(store, cfg):
    store.set_setting("card.ad_text", "new ad")
    store.set_setting("card.delete_original", "on")
    assert effective_setting(store, cfg, "card.ad_text") == "new ad"
    assert effective_setting(store, cfg, "card.delete_original") is True


def test_channel_override_beats_global(store, cfg):
    store.set_setting("card.delete_original", "on")
    store.set_setting("card.delete_original.9", "off")
    assert effective_setting(store, cfg, "card.delete_original", 9) is False
    assert effective_setting(store, cfg, "card.delete_original", 8) is True
    assert effective_setting(store, cfg, "card.delete_original") is True


def test_clear_returns_none(store, cfg):
    store.set_setting("card.ad_text", "")
    store.set_setting("card.footer_text", "")
    assert effective_setting(store, cfg, "card.ad_text") is None
    assert effective_setting(store, cfg, "card.footer_text") is None


def test_delete_original_parses_on_off(store, cfg):
    for raw, want in [("on", True), ("off", False), ("ON", True), ("true", True), ("False", False)]:
        store.set_setting("card.delete_original", raw)
        assert effective_setting(store, cfg, "card.delete_original") is want
    assert parse_on_off(" On ") is True
    with pytest.raises(ValueError):
        parse_on_off("maybe")


def test_unknown_key_raises(store, cfg):
    with pytest.raises(ValueError):
        effective_setting(store, cfg, "card.nope")
