import pytest

from zaizai.board_sync import sync_board
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

    async def exists(self, message_id):
        return message_id in self.alive

    async def send(self, mode, page, page_index):
        self.next_id += 1
        self.alive.add(self.next_id)
        self.calls.append(("send", page_index, self.next_id))
        return self.next_id

    async def edit(self, message_id, mode, page, page_index):
        self.calls.append(("edit", message_id, page_index))

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
    assert gw.calls == [("send", 0, 1001)]
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
