"""Keep the per-mode board messages in sync with the pages of entries."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Collection, Mapping, Sequence
from typing import Protocol

from zaizai.models import Entry, Mode
from zaizai.store import Store

log = logging.getLogger(__name__)


class BoardGateway(Protocol):
    async def send(self, mode: Mode, page: list[Entry], page_index: int) -> int: ...

    async def edit(
        self, message_id: int, mode: Mode, page: list[Entry], page_index: int
    ) -> bool:
        """Bring the message up to date; False if the message no longer exists."""
        ...

    async def delete(self, message_id: int) -> None: ...


@dataclass(frozen=True)
class PageState:
    """What a board message currently shows: content fingerprint and its time."""

    fingerprint: str
    changed_at: float


def plan_page_edit(
    cached: PageState | None, fingerprint: str, now: float
) -> PageState | None:
    """None when the message already shows this content (skip the edit);
    otherwise the new state to render, stamped with `now` (R19)."""
    if cached is not None and cached.fingerprint == fingerprint:
        return None
    return PageState(fingerprint, now)


def modes_for_deleted(
    deleted_ids: Collection[int],
    board_ids: Mapping[Mode, Sequence[int]],
    self_deleted: Collection[int],
) -> set[Mode]:
    """Modes whose stored board messages were deleted by someone else."""
    foreign = set(deleted_ids) - set(self_deleted)
    return {mode for mode, ids in board_ids.items() if foreign.intersection(ids)}


async def sync_board(
    store: Store, gateway: BoardGateway, mode: Mode, pages: list[list[Entry]]
) -> None:
    """Page i maps to the i-th stored message id; recreate, add or delete as needed."""
    old_ids = store.get_board_message_ids(mode)
    new_ids: list[int] = []
    try:
        for index, page in enumerate(pages):
            message_id = old_ids[index] if index < len(old_ids) else None
            if message_id is not None and await gateway.edit(
                message_id, mode, page, index
            ):
                new_ids.append(message_id)
            else:
                new_ids.append(await gateway.send(mode, page, index))
    except BaseException:
        # Record what we know (new ids so far + untouched old ones) so the
        # next refresh does not re-send and leave orphans.
        store.set_board_message_ids(mode, new_ids + old_ids[len(new_ids):])
        raise
    for extra in old_ids[len(pages):]:
        try:
            await gateway.delete(extra)
        except Exception:
            log.warning("could not delete board message %s", extra, exc_info=True)
    store.set_board_message_ids(mode, new_ids)
