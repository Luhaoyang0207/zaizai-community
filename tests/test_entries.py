from zaizai.entries import find_expired, paginate_entries, sort_for_board
from zaizai.models import Entry, Mode


def make(id_, updated_at=0.0):
    return Entry(id=id_, room_id=1, mode=Mode.RANKED, text="t", host_id=1,
                 card_channel_id=1, card_message_id=1, created_at=0.0,
                 updated_at=updated_at)


def test_expired_boundary():
    exact = make(1, updated_at=1000.0)
    over = make(2, updated_at=1000.0 - 1)
    now = 1000.0 + 30 * 60
    assert find_expired([exact, over], now, 30) == [over]
    assert find_expired([exact], now + 1, 30) == [exact]


def test_sort_newest_first_tiebreak_by_id():
    a, b, c = make(1, 10.0), make(2, 20.0), make(3, 20.0)
    assert sort_for_board([a, b, c]) == [c, b, a]


def test_paginate_empty_returns_one_empty_page():
    assert paginate_entries([], 10) == [[]]


def test_paginate_25_entries_per_page_10():
    pages = paginate_entries([make(i) for i in range(25)], 10)
    assert [len(p) for p in pages] == [10, 10, 5]


def test_paginate_exact_multiple():
    pages = paginate_entries([make(i) for i in range(20)], 10)
    assert [len(p) for p in pages] == [10, 10]
