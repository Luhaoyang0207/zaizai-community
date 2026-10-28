import pytest

from zaizai.models import Mode, Room
from zaizai.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "z.db"))
    s.init()
    yield s
    s.close()


def _room(room_id=100, mode=Mode.RANKED):
    return Room(room_id, mode, 1, 5, 10.0, False, None)


def test_upsert_entry_twice_keeps_one_row(store):
    store.add_room(_room())
    first = store.upsert_entry(100, Mode.RANKED, "a", 1, 2, 3, now=10.0)
    second = store.upsert_entry(100, Mode.RANKED, "b", 1, 2, 4, now=20.0)
    entries = store.list_entries(Mode.RANKED)
    assert len(entries) == 1
    assert entries[0].text == "b"
    assert entries[0].created_at == 10.0
    assert entries[0].updated_at == 20.0
    assert entries[0].card_message_id == 4
    assert second.id == first.id
    assert second == entries[0]


def test_delete_room_removes_entry(store):
    store.add_room(_room())
    store.upsert_entry(100, Mode.RANKED, "a", 1, 2, 3, now=1.0)
    store.delete_room(100)
    assert store.get_room(100) is None
    assert store.get_entry_by_room(100) is None


def test_delete_entry_by_room(store):
    store.add_room(_room())
    store.upsert_entry(100, Mode.RANKED, "a", 1, 2, 3, now=1.0)
    assert store.delete_entry_by_room(100) is True
    assert store.delete_entry_by_room(100) is False


def test_room_roundtrip_and_updates(store):
    store.add_room(_room(100, Mode.RANKED))
    store.add_room(_room(101, Mode.MATCH))
    store.set_locked(100, True)
    store.set_panel_message(100, 999)
    r = store.get_room(100)
    assert r.locked is True and r.panel_message_id == 999 and r.mode is Mode.RANKED
    assert [x.id for x in store.list_rooms()] == [100, 101]
    assert [x.id for x in store.list_rooms(Mode.MATCH)] == [101]


def test_list_entries_filters_by_mode(store):
    store.add_room(_room(100, Mode.RANKED))
    store.add_room(_room(101, Mode.MATCH))
    store.upsert_entry(100, Mode.RANKED, "r", 1, 2, 3, now=1.0)
    store.upsert_entry(101, Mode.MATCH, "m", 1, 2, 3, now=1.0)
    assert [e.text for e in store.list_entries(Mode.RANKED)] == ["r"]
    assert [e.text for e in store.list_entries(Mode.MATCH)] == ["m"]
    assert store.list_entries(Mode.OTHER) == []


def test_board_message_ids_roundtrip(store):
    assert store.get_board_message_ids(Mode.RANKED) == []
    store.set_board_message_ids(Mode.RANKED, [30, 10, 20])
    assert store.get_board_message_ids(Mode.RANKED) == [30, 10, 20]
    store.set_board_message_ids(Mode.RANKED, [5])
    assert store.get_board_message_ids(Mode.RANKED) == [5]
    assert store.get_board_message_ids(Mode.MATCH) == []


def test_state_survives_reopen(tmp_path):
    path = str(tmp_path / "z.db")
    s = Store(path)
    s.init()
    s.add_room(_room())
    s.upsert_entry(100, Mode.RANKED, "a", 1, 2, 3, now=1.0)
    s.set_board_message_ids(Mode.RANKED, [7, 8])
    s.add_category(Mode.RANKED, 42)
    s.set_setting("k", "v")
    s.close()

    s2 = Store(path)
    s2.init()
    try:
        assert s2.get_room(100) is not None
        assert s2.get_entry_by_room(100).text == "a"
        assert s2.get_board_message_ids(Mode.RANKED) == [7, 8]
        assert s2.list_categories(Mode.RANKED) == [42]
        assert s2.get_setting("k") == "v"
    finally:
        s2.close()


def test_settings_default_and_override(store):
    assert store.get_setting("x") is None
    assert store.get_setting("x", "d") == "d"
    store.set_setting("x", "1")
    store.set_setting("x", "2")
    assert store.get_setting("x", "d") == "2"


def test_categories_keep_insertion_order(store):
    for c in (30, 10, 20, 10):
        store.add_category(Mode.RANKED, c)
    assert store.list_categories(Mode.RANKED) == [30, 10, 20]
    assert store.list_categories(Mode.MATCH) == []
