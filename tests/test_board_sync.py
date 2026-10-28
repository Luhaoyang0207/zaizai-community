import pytest

from zaizai.board_sync import PageState, modes_for_deleted, plan_page_edit, sync_board
from zaizai.models import Entry, Mode
from zaizai.store import Store


class GatewayError(Exception):
    pass


class FakeGateway:
    def __init__(self, existing=(), delete_raises=False):
        self.alive = set(existing)
        self.delete_raises = delete_raises
        self.next_id = 1000
        self.calls: list[tuple] = []

    async def send(self, mode, page, page_index):
        self.next_id += 1
        self.alive.add(self.next_id)
        self.calls.append(("send", page_index, self.next_id))
        return self.next_id

    async def edit(self, message_id, mode, page, page_index):
        if message_id not in self.alive:
            self.calls.append(("edit-missing", message_id, page_index))
            return False
        self.calls.append(("edit", message_id, page_index))
        return True

    async def delete(self, message_id):
        self.calls.append(("delete", message_id))
        if self.delete_raises:
            raise GatewayError("Unknown Message")
        self.alive.discard(message_id)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init()
    yield s
    s.close()


def entry(i: int) -> Entry:
    return Entry(i, 1, Mode.RANKED, f"e{i}", 1, 1, i, 1.0, 1.0)


async def test_first_sync_sends_one_message_even_when_empty(store):
    gw = FakeGateway()
    await sync_board(store, gw, Mode.RANKED, [[]])
    assert gw.calls == [("send", 0, 1001)]
    assert store.get_board_message_ids(Mode.RANKED) == [1001]


async def test_existing_message_is_edited_not_resent(store):
    store.set_board_message_ids(Mode.RANKED, [50])
    gw = FakeGateway(existing={50})
    await sync_board(store, gw, Mode.RANKED, [[entry(1)]])
    assert gw.calls == [("edit", 50, 0)]
    assert store.get_board_message_ids(Mode.RANKED) == [50]


async def test_manually_deleted_message_is_recreated_and_id_stored(store):
    store.set_board_message_ids(Mode.RANKED, [50])
    gw = FakeGateway(existing=set())
    await sync_board(store, gw, Mode.RANKED, [[entry(1)]])
    assert gw.calls == [("edit-missing", 50, 0), ("send", 0, 1001)]
    assert store.get_board_message_ids(Mode.RANKED) == [1001]


async def test_grows_to_more_pages(store):
    store.set_board_message_ids(Mode.RANKED, [50])
    gw = FakeGateway(existing={50})
    await sync_board(store, gw, Mode.RANKED, [[entry(1)], [entry(2)], [entry(3)]])
    assert gw.calls == [("edit", 50, 0), ("send", 1, 1001), ("send", 2, 1002)]
    assert store.get_board_message_ids(Mode.RANKED) == [50, 1001, 1002]


async def test_shrinks_deletes_extra_messages(store):
    store.set_board_message_ids(Mode.RANKED, [50, 51, 52])
    gw = FakeGateway(existing={50, 51, 52})
    await sync_board(store, gw, Mode.RANKED, [[entry(1)]])
    assert ("edit", 50, 0) in gw.calls
    assert ("delete", 51) in gw.calls and ("delete", 52) in gw.calls
    assert store.get_board_message_ids(Mode.RANKED) == [50]


async def test_delete_error_on_missing_message_is_ignored(store):
    store.set_board_message_ids(Mode.RANKED, [50, 51])
    gw = FakeGateway(existing={50}, delete_raises=True)
    await sync_board(store, gw, Mode.RANKED, [[entry(1)]])
    assert store.get_board_message_ids(Mode.RANKED) == [50]


async def test_partial_failure_persists_ids_sent_so_far(store):
    class Failing(FakeGateway):
        async def send(self, mode, page, page_index):
            if page_index == 1:
                raise GatewayError("boom")
            return await super().send(mode, page, page_index)

    gw = Failing()
    with pytest.raises(GatewayError):
        await sync_board(store, gw, Mode.RANKED, [[entry(1)], [entry(2)]])
    assert store.get_board_message_ids(Mode.RANKED) == [1001]


async def test_partial_failure_on_edit_keeps_untouched_old_ids(store):
    store.set_board_message_ids(Mode.RANKED, [50, 51])

    class Failing(FakeGateway):
        async def edit(self, message_id, mode, page, page_index):
            if message_id == 51:
                raise GatewayError("boom")
            return await super().edit(message_id, mode, page, page_index)

    gw = Failing(existing={51})
    with pytest.raises(GatewayError):
        await sync_board(store, gw, Mode.RANKED, [[entry(1)], [entry(2)]])
    # page 0 was re-sent (50 was gone), page 1's id is kept for the next try
    assert store.get_board_message_ids(Mode.RANKED) == [1001, 51]


def test_plan_page_edit_first_time_edits_with_now():
    assert plan_page_edit(None, "fp", 100.0) == PageState("fp", 100.0)


def test_plan_page_edit_unchanged_content_is_skipped():
    assert plan_page_edit(PageState("fp", 50.0), "fp", 100.0) is None


def test_plan_page_edit_changed_content_restamps():
    assert plan_page_edit(PageState("old", 50.0), "new", 100.0) == PageState(
        "new", 100.0
    )


def test_modes_for_deleted_matches_board_ids():
    ids = {Mode.RANKED: [50, 51], Mode.MATCH: [60]}
    assert modes_for_deleted({51}, ids, set()) == {Mode.RANKED}
    assert modes_for_deleted({51, 60}, ids, set()) == {Mode.RANKED, Mode.MATCH}


def test_modes_for_deleted_ignores_unrelated_and_self_deleted():
    ids = {Mode.RANKED: [50, 51]}
    assert modes_for_deleted({999}, ids, set()) == set()
    assert modes_for_deleted({51}, ids, {51}) == set()
    assert modes_for_deleted(set(), ids, set()) == set()
