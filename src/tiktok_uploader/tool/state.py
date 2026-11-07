"""Durable submission boundary, process lock, and verified file moves."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plan import ToolError, fingerprint


class Ledger:
    def __init__(self, home: Path):
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        home.chmod(0o700)
        self.lock = (home / "run.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            raise ToolError(
                "Another tiktok-tool process is using this state directory"
            ) from exc
        self.db = sqlite3.connect(home / "state.sqlite3")
        (home / "state.sqlite3").chmod(0o600)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, record TEXT NOT NULL)"
        )
        self.db.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT record FROM jobs WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, **fields: Any) -> dict[str, Any]:
        record = self.get(key) or {"key": key}
        record.update(fields)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?,?)",
            (key, json.dumps(record, ensure_ascii=False)),
        )
        self.db.commit()
        return record

    def records(self) -> list[dict[str, Any]]:
        return [
            json.loads(row[0])
            for row in self.db.execute("SELECT record FROM jobs ORDER BY key")
        ]

    def close(self) -> None:
        self.db.close()
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.lock.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def read_records(home: Path) -> list[dict[str, Any]]:
    """Read committed status even while a publisher holds the process lock."""
    database = home / "state.sqlite3"
    if not database.exists():
        return []
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as db:
        return [
            json.loads(row[0])
            for row in db.execute("SELECT record FROM jobs ORDER BY key")
        ]


def move_verified(item: dict[str, Any], record: dict[str, Any]) -> str | None:
    if record.get("status") not in {"scheduled", "published"} or not record.get(
        "post_url"
    ):
        raise ToolError("Refusing to move a source before publication is verified")
    destination = item.get("destination")
    if not destination:
        return None
    source, target = Path(item["source"]), Path(destination)
    if target.exists():
        if (
            record.get("move_started") == str(target)
            and fingerprint(target) == item["sha256"]
        ):
            if source.exists():
                if fingerprint(source) != item["sha256"]:
                    raise ToolError("Source changed during an interrupted move")
                source.unlink()
            return str(target)
        raise ToolError("DONE destination already exists; refusing overwrite")
    if fingerprint(source) != item["sha256"]:
        raise ToolError("Source fingerprint changed; refusing move")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also works across volumes and refuses overwrite races.
    try:
        with source.open("rb") as src, target.open("xb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        if fingerprint(target) != item["sha256"]:
            raise ToolError("Copied file fingerprint does not match")
        source.unlink()
    except BaseException:
        # Preserve the source; a partial destination is reported for manual review.
        raise
    return str(target)
