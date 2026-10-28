import sqlite3

from zaizai.models import Entry, Mode, Room

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    locked INTEGER NOT NULL DEFAULT 0,
    panel_message_id INTEGER
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    text TEXT NOT NULL,
    host_id INTEGER NOT NULL,
    card_channel_id INTEGER NOT NULL,
    card_message_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS board_messages (
    mode TEXT NOT NULL,
    page INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    PRIMARY KEY (mode, page)
);
CREATE TABLE IF NOT EXISTS categories (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    UNIQUE (mode, category_id)
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _room(r: sqlite3.Row) -> Room:
    return Room(
        id=r["id"],
        mode=Mode(r["mode"]),
        owner_id=r["owner_id"],
        category_id=r["category_id"],
        created_at=r["created_at"],
        locked=bool(r["locked"]),
        panel_message_id=r["panel_message_id"],
    )


def _entry(r: sqlite3.Row) -> Entry:
    return Entry(
        id=r["id"],
        room_id=r["room_id"],
        mode=Mode(r["mode"]),
        text=r["text"],
        host_id=r["host_id"],
        card_channel_id=r["card_channel_id"],
        card_message_id=r["card_message_id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


class Store:
    """SQLite-backed persistent state. Single connection, autocommit."""

    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(
            path, check_same_thread=False, isolation_level=None
        )
        self._db.row_factory = sqlite3.Row

    def close(self) -> None:
        self._db.close()

    def init(self) -> None:
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)

    # rooms
    def add_room(self, room: Room) -> None:
        self._db.execute(
            "INSERT INTO rooms (id, mode, owner_id, category_id, created_at,"
            " locked, panel_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                room.id,
                room.mode.value,
                room.owner_id,
                room.category_id,
                room.created_at,
                int(room.locked),
                room.panel_message_id,
            ),
        )

    def get_room(self, room_id: int) -> Room | None:
        r = self._db.execute(
            "SELECT * FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()
        return _room(r) if r else None

    def list_rooms(self, mode: Mode | None = None) -> list[Room]:
        if mode is None:
            rows = self._db.execute("SELECT * FROM rooms ORDER BY created_at, id")
        else:
            rows = self._db.execute(
                "SELECT * FROM rooms WHERE mode = ? ORDER BY created_at, id",
                (mode.value,),
            )
        return [_room(r) for r in rows.fetchall()]

    def set_locked(self, room_id: int, locked: bool) -> None:
        self._db.execute(
            "UPDATE rooms SET locked = ? WHERE id = ?", (int(locked), room_id)
        )

    def set_panel_message(self, room_id: int, message_id: int) -> None:
        self._db.execute(
            "UPDATE rooms SET panel_message_id = ? WHERE id = ?",
            (message_id, room_id),
        )

    def delete_room(self, room_id: int) -> None:
        self._db.execute("BEGIN")
        try:
            self._db.execute("DELETE FROM entries WHERE room_id = ?", (room_id,))
            self._db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    # entries
    def upsert_entry(
        self,
        room_id: int,
        mode: Mode,
        text: str,
        host_id: int,
        card_channel_id: int,
        card_message_id: int,
        now: float,
    ) -> Entry:
        self._db.execute(
            "INSERT INTO entries (room_id, mode, text, host_id, card_channel_id,"
            " card_message_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(room_id) DO UPDATE SET mode = excluded.mode,"
            " text = excluded.text, host_id = excluded.host_id,"
            " card_channel_id = excluded.card_channel_id,"
            " card_message_id = excluded.card_message_id,"
            " updated_at = excluded.updated_at",
            (room_id, mode.value, text, host_id, card_channel_id,
             card_message_id, now, now),
        )
        entry = self.get_entry_by_room(room_id)
        assert entry is not None
        return entry

    def get_entry_by_room(self, room_id: int) -> Entry | None:
        r = self._db.execute(
            "SELECT * FROM entries WHERE room_id = ?", (room_id,)
        ).fetchone()
        return _entry(r) if r else None

    def delete_entry_by_room(self, room_id: int) -> bool:
        cur = self._db.execute("DELETE FROM entries WHERE room_id = ?", (room_id,))
        return cur.rowcount > 0

    def list_entries(self, mode: Mode) -> list[Entry]:
        rows = self._db.execute(
            "SELECT * FROM entries WHERE mode = ? ORDER BY created_at, id",
            (mode.value,),
        ).fetchall()
        return [_entry(r) for r in rows]

    # board messages (ordered by page)
    def get_board_message_ids(self, mode: Mode) -> list[int]:
        rows = self._db.execute(
            "SELECT message_id FROM board_messages WHERE mode = ? ORDER BY page",
            (mode.value,),
        ).fetchall()
        return [r["message_id"] for r in rows]

    def set_board_message_ids(self, mode: Mode, ids: list[int]) -> None:
        self._db.execute("BEGIN")
        try:
            self._db.execute(
                "DELETE FROM board_messages WHERE mode = ?", (mode.value,)
            )
            self._db.executemany(
                "INSERT INTO board_messages (mode, page, message_id)"
                " VALUES (?, ?, ?)",
                [(mode.value, i, mid) for i, mid in enumerate(ids)],
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    # categories (insertion order)
    def list_categories(self, mode: Mode) -> list[int]:
        rows = self._db.execute(
            "SELECT category_id FROM categories WHERE mode = ? ORDER BY seq",
            (mode.value,),
        ).fetchall()
        return [r["category_id"] for r in rows]

    def add_category(self, mode: Mode, category_id: int) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO categories (mode, category_id) VALUES (?, ?)",
            (mode.value, category_id),
        )

    # settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        r = self._db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
