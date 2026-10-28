from collections.abc import Callable, Collection, Mapping
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


def partition_stale(
    stale: Collection[int], still_exists: Callable[[int], bool]
) -> tuple[frozenset[int], frozenset[int]]:
    """(rooms truly gone, rooms moved out of the managed categories but still alive)."""
    moved = frozenset(rid for rid in stale if still_exists(rid))
    return frozenset(stale) - moved, moved
