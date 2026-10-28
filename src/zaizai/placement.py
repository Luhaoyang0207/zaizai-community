import re
from collections.abc import Iterable, Sequence


def pick_category(counts: Sequence[int], max_per_category: int) -> int | None:
    """Index of the first non-full category, or None if a new one is needed."""
    for i, count in enumerate(counts):
        if count < max_per_category:
            return i
    return None


def next_room_name(template: str, existing_names: Iterable[str]) -> str:
    """Fill the template with the smallest unused positive integer."""
    before, sep, after = template.partition("{n}")
    pattern = re.compile(re.escape(before) + r"(\d+)" + re.escape(after))
    used = set()
    for name in existing_names:
        m = pattern.fullmatch(name)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return template.replace("{n}", str(n))
