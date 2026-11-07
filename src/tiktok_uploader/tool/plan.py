"""Offline, reviewable plans. No browser or network side effects."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TIMEZONE = "Asia/Ho_Chi_Minh"


class ToolError(Exception):
    """An actionable error safe to show without browser/session internals."""


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ToolError("Use an ISO date/time, e.g. 2026-11-09T10:30:00+07:00") from exc
    if result.tzinfo is None:
        raise ToolError("Schedule must include timezone, e.g. +07:00")
    if result.second or result.microsecond or result.minute % 5:
        raise ToolError("Schedule must use a five-minute boundary with zero seconds")
    return result.astimezone(ZoneInfo(TIMEZONE))


def validate_time(value: str | None, now: datetime | None = None) -> None:
    if value is None:
        return
    when = parse_time(value)
    current = now or datetime.now(ZoneInfo(TIMEZONE))
    if not timedelta(minutes=20) <= when - current <= timedelta(days=10):
        raise ToolError(
            "Schedule must be 20 minutes to 10 days ahead; time is never shifted automatically"
        )


def job_key(account: str, sha256: str) -> str:
    return hashlib.sha256(f"{account.lower()}:{sha256}".encode()).hexdigest()


def make_plan(
    files: list[str],
    account: str,
    captions: list[str],
    *,
    start: str | None = None,
    interval: int = 30,
    product_policy: str = "required",
    done_dir: str | None = None,
) -> dict[str, Any]:
    account = account.removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_.]+", account):
        raise ToolError("Provide the exact TikTok username")
    if not files or len(files) != len(captions):
        raise ToolError("Provide one caption for each explicit video file")
    if product_policy not in {"required", "if-available", "none"}:
        raise ToolError("Unknown product policy")
    if interval < 5 or interval % 5:
        raise ToolError("Interval must be a positive multiple of five minutes")
    first = parse_time(start) if start else None
    items = []
    hashes: set[str] = set()
    for index, (name, caption) in enumerate(zip(files, captions)):
        path = Path(name).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in {
            ".mp4",
            ".mov",
            ".webm",
            ".m4v",
        }:
            raise ToolError(f"Expected one video file: {path.name}")
        if not isinstance(caption, str) or not caption.strip() or len(caption) > 2200:
            raise ToolError("Each caption must contain 1–2200 characters")
        sha256 = fingerprint(path)
        if sha256 in hashes:
            raise ToolError("Duplicate video bytes in this plan")
        hashes.add(sha256)
        match = re.match(r"^([0-9]+)_", path.name)
        if product_policy != "none" and not match:
            raise ToolError(f"No product ID prefix in {path.name}")
        schedule = (
            (first + timedelta(minutes=index * interval)).isoformat() if first else None
        )
        validate_time(schedule)
        destination = (
            str(Path(done_dir).expanduser().resolve() / path.name) if done_dir else None
        )
        if destination == str(path):
            raise ToolError("DONE destination must differ from source")
        items.append(
            {
                "key": job_key(account, sha256),
                "source": str(path),
                "sha256": sha256,
                "caption": caption.strip(),
                "product_id": match.group(1)
                if match and product_policy != "none"
                else None,
                "scheduled_at": schedule,
                "ai_label": True,
                "destination": destination,
            }
        )
    return {
        "version": 1,
        "account": account,
        "timezone": TIMEZONE,
        "product_policy": product_policy,
        "items": items,
    }


def read_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text())
    if plan.get("version") != 1 or plan.get("timezone") != TIMEZONE:
        raise ToolError("Unsupported plan version or timezone")
    if plan.get("product_policy") not in {"required", "if-available", "none"}:
        raise ToolError("Invalid product policy")
    if not re.fullmatch(r"[A-Za-z0-9_.]+", plan.get("account", "")):
        raise ToolError("Invalid account")
    if not plan.get("items"):
        raise ToolError("Empty plan")
    seen = set()
    for item in plan["items"]:
        if item.get("ai_label") is not True:
            raise ToolError("AI label is required by this tool")
        if (
            not isinstance(item.get("caption"), str)
            or not 1 <= len(item["caption"].strip()) <= 2200
        ):
            raise ToolError("Invalid caption")
        sha = item.get("sha256", "")
        if not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ToolError("Invalid video fingerprint")
        if item.get("key") != job_key(plan["account"], sha) or item["key"] in seen:
            raise ToolError("Invalid or duplicate job key")
        seen.add(item["key"])
        product = item.get("product_id")
        if plan["product_policy"] != "none" and (
            not isinstance(product, str) or not product.isdigit()
        ):
            raise ToolError("Product ID must remain a digit string")
        if plan["product_policy"] != "none":
            prefix = re.match(r"^([0-9]+)_", Path(item["source"]).name)
            if not prefix or prefix.group(1) != product:
                raise ToolError("Product ID does not match the source filename prefix")
        if item.get("scheduled_at") is not None:
            parse_time(item["scheduled_at"])
    return plan
