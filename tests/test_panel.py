import re

import pytest

from zaizai.cogs.panel import (
    PANEL_TEMPLATE,
    lock_label,
    owner_denial,
    panel_custom_id,
    parse_panel_custom_id,
    role_connect_changes,
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


EVERYONE, VERIFIED, MOD = "everyone", "verified", "mod"


def test_lock_denies_everyone_and_every_role_that_allows_connect():
    changes = role_connect_changes(
        True,
        EVERYONE,
        room_connect={EVERYONE: None, VERIFIED: True, MOD: None},
        category_connect={VERIFIED: True},
    )
    assert changes == {EVERYONE: False, VERIFIED: False}


def test_lock_without_everyone_overwrite_still_denies_everyone():
    assert role_connect_changes(True, EVERYONE, {}, {}) == {EVERYONE: False}


def test_lock_already_locked_changes_nothing():
    changes = role_connect_changes(
        True, EVERYONE, {EVERYONE: False, VERIFIED: False}, {VERIFIED: True}
    )
    assert changes == {}


def test_unlock_restores_from_category():
    changes = role_connect_changes(
        False,
        EVERYONE,
        room_connect={EVERYONE: False, VERIFIED: False, MOD: False},
        category_connect={EVERYONE: False, VERIFIED: True},
    )
    # everyone stays denied like its category; verified back to allow;
    # mod has no category overwrite -> neutral
    assert changes == {VERIFIED: True, MOD: None}


def test_unlock_without_category_clears_denies():
    changes = role_connect_changes(
        False, EVERYONE, {EVERYONE: False, VERIFIED: False, MOD: True}, {}
    )
    assert changes == {EVERYONE: None, VERIFIED: None}
