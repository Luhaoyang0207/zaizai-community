from zaizai.cogs.voice_rooms import classify_transition, overflow_category_name

ENT = {10, 11}
ROOMS = {100, 101}


def _t(b, a):
    t = classify_transition(b, a, ENT, ROOMS)
    return (t.entrance_joined, t.left_room, t.joined_room)


def test_no_change():
    assert _t(100, 100) == (None, None, None)


def test_join_entrance():
    assert _t(None, 10) == (10, None, None)


def test_entrance_to_room():
    assert _t(10, 100) == (None, None, 100)


def test_room_to_room():
    assert _t(100, 101) == (None, 100, 101)


def test_leave_room():
    assert _t(100, None) == (None, 100, None)


def test_unmanaged_channels_ignored():
    assert _t(55, 66) == (None, None, None)


def test_room_to_entrance():
    assert _t(100, 11) == (11, 100, None)


def test_overflow_name():
    assert overflow_category_name("Ranked", 1) == "Ranked 2"
    assert overflow_category_name("Ranked", 2) == "Ranked 3"
