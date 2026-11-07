"""CLI for explicit plans, isolated login, publication, and reconciliation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .plan import ToolError, make_plan, read_plan
from .state import Ledger, read_records
from .studio import StudioSession
from .workflow import reconcile_item, run_item


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="tiktok-tool",
        description="Verified TikTok Studio publisher; one file per post",
    )
    root.add_argument(
        "--home",
        type=Path,
        default=Path(
            os.environ.get("TIKTOK_TOOL_HOME", Path.home() / ".local/share/tiktok-tool")
        ),
    )
    root.add_argument(
        "--browser-executable",
        default=os.environ.get("TIKTOK_BROWSER_EXECUTABLE"),
        help="Optional Chrome/Cốc Cốc binary; always uses an isolated profile",
    )
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser(
        "plan", help="Create a reviewable JSON plan, offline; never posts"
    )
    plan.add_argument("files", nargs="+")
    plan.add_argument("--account", required=True)
    captions = plan.add_mutually_exclusive_group(required=True)
    captions.add_argument(
        "--caption",
        action="append",
        help="One per file; a single caption applies to all explicit files",
    )
    captions.add_argument(
        "--captions-json",
        type=Path,
        help="JSON array with exactly one caption per file",
    )
    plan.add_argument(
        "--start", help="ISO timestamp with timezone; omit for immediate posting"
    )
    plan.add_argument("--interval", type=int, default=30)
    plan.add_argument(
        "--product-policy",
        choices=["required", "if-available", "none"],
        default="required",
    )
    plan.add_argument(
        "--done-dir", help="Move only after a new post and schedule are verified"
    )
    plan.add_argument("--out", type=Path, required=True)
    for name in ("login", "doctor"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--account", required=True)
    commands.add_parser("status", help="Read local publication ledger, no browser")
    for name in ("run", "reconcile"):
        cmd = commands.add_parser(name)
        cmd.add_argument("plan", type=Path)
        cmd.add_argument(
            "--job", help="One job key from the plan; otherwise process sequentially"
        )
        if name == "run":
            cmd.add_argument(
                "--submit",
                action="store_true",
                help="Actually upload and publish the reviewed plan; omit for offline inspection",
            )
            cmd.add_argument(
                "--wait-checks",
                type=int,
                default=900,
                help="Maximum seconds to wait for TikTok checks; never disables checks",
            )
    return root


def execute(args: argparse.Namespace) -> int:
    if args.command == "plan":
        captions = (
            json.loads(args.captions_json.read_text())
            if args.captions_json
            else args.caption
        )
        if not isinstance(captions, list):
            raise ToolError("Captions JSON must be an array")
        if len(captions) == 1 and args.caption:
            captions *= len(args.files)
        plan = make_plan(
            args.files,
            args.account,
            captions,
            start=args.start,
            interval=args.interval,
            product_policy=args.product_policy,
            done_dir=args.done_dir,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite a plan already used by another run.
        with args.out.open("x") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
        args.out.chmod(0o600)
        output(
            {
                "status": "planned",
                "plan": str(args.out.resolve()),
                "posts": len(plan["items"]),
                "publishing": False,
            }
        )
        return 0
    if args.command in {"login", "doctor"}:
        # Reuse account validation without touching media or credentials.
        import re

        account = args.account.removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_.]+", account):
            raise ToolError("Invalid TikTok username")
        with (
            Ledger(args.home),
            StudioSession(
                args.home / "profiles" / account.lower(), args.browser_executable
            ) as driver,
        ):
            if args.command == "login":
                driver.page.goto(
                    "https://www.tiktok.com/login", wait_until="domcontentloaded"
                )
                print(
                    "Đăng nhập TikTok trong cửa sổ riêng. Tự xử lý CAPTCHA nếu có, sau đó nhấn Enter ở terminal.",
                    flush=True,
                )
                input()
            driver.verify_account(account)
            output({"status": "account_verified", "account": account})
        return 0
    if args.command == "status":
        output(read_records(args.home))
        return 0
    plan = read_plan(args.plan)
    items = [item for item in plan["items"] if not args.job or item["key"] == args.job]
    if not items:
        raise ToolError("Job key is not in this plan")
    if args.command == "run" and not args.submit:
        output({"status": "inspection_only", "publishing": False, "plan": plan})
        return 0
    if args.command == "run" and not 1 <= args.wait_checks <= 3600:
        raise ToolError("wait-checks must be 1–3600 seconds")
    with (
        Ledger(args.home) as ledger,
        StudioSession(
            args.home / "profiles" / plan["account"].lower(), args.browser_executable
        ) as driver,
    ):
        driver.verify_account(plan["account"])
        for index, item in enumerate(items, 1):
            output(
                {
                    "status": "starting",
                    "index": index,
                    "total": len(items),
                    "file": Path(item["source"]).name,
                    "key": item["key"],
                }
            )
            try:
                result = (
                    run_item(driver, ledger, plan, item, args.wait_checks)
                    if args.command == "run"
                    else reconcile_item(driver, ledger, plan, item)
                )
                output(result)
            except BaseException:
                evidence = args.home / "evidence" / item["key"]
                evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    target = evidence / "last-screen.png"
                    driver.page.screenshot(path=str(target), full_page=True)
                    target.chmod(0o600)
                except Exception:
                    pass
                raise
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        return execute(args)
    except KeyboardInterrupt:
        output(
            {
                "status": "interrupted",
                "message": "Inspect ledger before retrying any submission",
            }
        )
        return 130
    except Exception as exc:
        # Playwright traces may contain page URLs and internals. Keep terminal
        # errors short; never print cookies, storage_state, or session tokens.
        message = (
            str(exc)
            if isinstance(exc, (ToolError, FileExistsError, FileNotFoundError))
            else type(exc).__name__
        )
        output({"status": "stopped", "message": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
