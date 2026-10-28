from collections.abc import Iterable, Sequence

from zaizai.models import Entry


def find_expired(entries: Iterable[Entry], now: float, timeout_min: int) -> list[Entry]:
    """Entries idle for strictly longer than the timeout, in input order."""
    limit = timeout_min * 60
    return [e for e in entries if now - e.updated_at > limit]


def sort_for_board(entries: Iterable[Entry]) -> list[Entry]:
    """Newest update first; higher id first on ties."""
    return sorted(entries, key=lambda e: (e.updated_at, e.id), reverse=True)


def paginate_entries(entries: Sequence[Entry], per_page: int) -> list[list[Entry]]:
    """Split into pages; always returns at least one (possibly empty) page."""
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    if not entries:
        return [[]]
    return [list(entries[i:i + per_page]) for i in range(0, len(entries), per_page)]
