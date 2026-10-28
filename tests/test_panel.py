import re

import pytest

from zaizai.cogs.panel import (
    PANEL_TEMPLATE,
    lock_label,
    owner_denial,
    panel_custom_id,
    parse_panel_custom_id,
)
from zaizai.models import Mode, Room


def _room(owner_id: int = 7) -> Room:
    return Room(
        id=555,
        mode=Mode.RANKED,
        owner_id=owner_id,
        category_id=1,
        created_at=0.0,
        locked=False,
        panel_message_id=None,
    )


@pytest.mark.parametrize("action", ["lock", "full"])
def test_custom_id_round_trip(action):
    cid = panel_custom_id(action, 123456789012345678)
    assert parse_panel_custom_id(cid) == (action, 123456789012345678)
    m = re.fullmatch(PANEL_TEMPLATE, cid)
    assert m is not None
    assert m["action"] == action and int(m["room"]) == 123456789012345678


def test_custom_id_fits_discord_limit():
    assert len(panel_custom_id("lock", 2**64 - 1)) <= 100


@pytest.mark.parametrize(
    "cid",
    ["zaizai:panel:kick:1", "zaizai:panel:lock:", "zaizai:panel:lock:12x", "other:lock:1"],
)
def test_parse_rejects_foreign_ids(cid):
    assert parse_panel_custom_id(cid) is None


def test_build_rejects_unknown_action():
    with pytest.raises(ValueError):
        panel_custom_id("kick", 1)


def test_lock_label():
    assert lock_label(False) == "🔓开"
    assert lock_label(True) == "🔒锁"


def test_owner_denial_missing_room():
    assert owner_denial(None, 7) == "房间已不存在"


def test_owner_denial_not_owner():
    assert owner_denial(_room(owner_id=7), 8) == "只有房主可以使用面板"


def test_owner_denial_owner_allowed():
    assert owner_denial(_room(owner_id=7), 7) is None
