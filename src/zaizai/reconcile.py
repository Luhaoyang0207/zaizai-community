from collections.abc import Collection, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ReconcileResult:
    stale: frozenset[int]
    adopt: frozenset[int]
    remove: frozenset[int]


def reconcile(db_room_ids: Collection[int], live_rooms: Mapping[int, int]) -> ReconcileResult:
    """Compare tracked rooms with live voice channels (channel id -> member count)."""
    tracked = set(db_room_ids)
    stale = tracked - live_rooms.keys()
    untracked = {cid: n for cid, n in live_rooms.items() if cid not in tracked}
    adopt = {cid for cid, n in untracked.items() if n > 0}
    remove = set(untracked) - adopt
    return ReconcileResult(frozenset(stale), frozenset(adopt), frozenset(remove))
