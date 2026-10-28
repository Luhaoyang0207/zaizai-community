"""Entry point: `python -m zaizai`."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .bot import ZaizaiBot
from .config import load_config
from .store import Store


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN is not set; refusing to start.", file=sys.stderr)
        return 1
    cfg = load_config(os.environ.get("ZAIZAI_CONFIG", "config/settings.toml"))
    db_path = Path(os.environ.get("ZAIZAI_DB_PATH", "data/zaizai.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(str(db_path))
    store.init()
    bot = ZaizaiBot(cfg, store)
    bot.run(token, log_handler=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
