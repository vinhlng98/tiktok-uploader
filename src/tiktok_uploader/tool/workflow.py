"""Submission state machine, independent of the browser adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .plan import ToolError, fingerprint, validate_time
from .state import Ledger, move_verified


class Driver(Protocol):
    def baseline(self, account: str, caption: str) -> list[str]: ...
    def prepare(
        self, item: dict[str, Any], policy: str, check_timeout: int
    ) -> dict[str, Any]: ...
    def audit(self, item: dict[str, Any], product: dict[str, Any]) -> None: ...
    def submit(self, item: dict[str, Any]) -> None: ...
    def verify_result(
        self, account: str, item: dict[str, Any], baseline: list[str]
    ) -> dict[str, Any]: ...
    def reconcile(
        self, account: str, item: dict[str, Any], baseline: list[str]
    ) -> dict[str, Any]: ...


def finish_move(
    ledger: Ledger, item: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    if item.get("destination") and not record.get("moved_to"):
        if (
            Path(item["destination"]).exists()
            and record.get("move_started") != item["destination"]
        ):
            raise ToolError("DONE destination already exists; refusing overwrite")
        record = ledger.put(item["key"], move_started=item["destination"])
        moved = move_verified(item, record)
        record = ledger.put(item["key"], moved_to=moved)
    return record


def run_item(
    driver: Driver,
    ledger: Ledger,
    plan: dict[str, Any],
    item: dict[str, Any],
    check_timeout: int,
) -> dict[str, Any]:
    key = item["key"]
    old = ledger.get(key)
    if old and old["status"] in {"scheduled", "published"}:
        return finish_move(ledger, item, old)
    if old and old["status"] in {"submitting", "unverified", "external_draft"}:
        raise ToolError(
            "This video needs reconciliation/manual review; refusing another submission"
        )
    source = Path(item["source"])
    if not source.is_file() or fingerprint(source) != item["sha256"]:
        raise ToolError("Source missing or changed since plan creation")
    validate_time(item.get("scheduled_at"))
    submitted = False
    try:
        baseline = driver.baseline(plan["account"], item["caption"])
        ledger.put(
            key,
            status="preparing",
            account=plan["account"],
            item=item,
            baseline=baseline,
        )
        product = driver.prepare(item, plan["product_policy"], check_timeout)
        driver.audit(item, product)
        # Commit the ambiguous boundary before the only publish click.
        ledger.put(key, status="submitting", product=product, ai_verified=True)
        submitted = True
        driver.submit(item)
        result = driver.verify_result(plan["account"], item, baseline)
        record = ledger.put(key, **result)
    except BaseException as exc:
        reason = str(exc) if isinstance(exc, ToolError) else type(exc).__name__
        ledger.put(
            key,
            status="unverified" if submitted else "failed_before_submit",
            reason=reason,
        )
        raise
    # Move errors must never downgrade a verified publication to retryable.
    return finish_move(ledger, item, record)


def reconcile_item(
    driver: Driver, ledger: Ledger, plan: dict[str, Any], item: dict[str, Any]
) -> dict[str, Any]:
    record = ledger.get(item["key"])
    if not record:
        raise ToolError("No prior submission to reconcile")
    if record["status"] in {"scheduled", "published"}:
        return finish_move(ledger, item, record)
    if record["status"] not in {"submitting", "unverified"}:
        raise ToolError(
            "No ambiguous submission to reconcile; external drafts require manual handling"
        )
    result = driver.reconcile(plan["account"], record["item"], record["baseline"])
    record = ledger.put(item["key"], **result)
    return finish_move(ledger, item, record)
