from zaizai.reconcile import ReconcileResult, reconcile


def test_stale_room_detected():
    r = reconcile({1, 2}, {1: 3})
    assert r == ReconcileResult(frozenset({2}), frozenset(), frozenset())


def test_untracked_nonempty_is_adopted():
    r = reconcile(set(), {5: 2})
    assert r.adopt == frozenset({5}) and not r.remove and not r.stale


def test_untracked_empty_is_removed():
    r = reconcile(set(), {5: 0})
    assert r.remove == frozenset({5}) and not r.adopt and not r.stale


def test_tracked_and_live_untouched():
    r = reconcile({1}, {1: 0})
    assert r == ReconcileResult(frozenset(), frozenset(), frozenset())


def test_all_empty_inputs():
    assert reconcile([], {}) == ReconcileResult(frozenset(), frozenset(), frozenset())
