"""TikTok Studio adapter. Uses visible controls; never forces a publish click."""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Locator, Page, sync_playwright

from tiktok_uploader import config

from .plan import TIMEZONE, ToolError, parse_time, validate_time

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video"
CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"


def normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def unique_visible(locator: Locator, label: str) -> Locator:
    choices = [
        locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()
    ]
    if len(choices) != 1:
        raise ToolError(
            f"Cannot identify exactly one visible {label}; UI adapter needs review"
        )
    return choices[0]


class StudioSession:
    """An isolated persistent profile, never the user's normal browser profile."""

    def __init__(self, profile: Path, executable: str | None = None):
        self.profile = profile
        self.executable = executable

    def __enter__(self) -> StudioDriver:
        self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.profile.chmod(0o700)
        self.playwright = sync_playwright().start()
        options: dict[str, Any] = {
            "headless": False,
            "locale": "en-US",
            "timezone_id": TIMEZONE,
            "viewport": {"width": 1440, "height": 1000},
        }
        if self.executable:
            options["executable_path"] = self.executable
        try:
            self.context: BrowserContext = (
                self.playwright.chromium.launch_persistent_context(
                    str(self.profile), **options
                )
            )
        except BaseException:
            self.playwright.stop()
            raise
        self.page = (
            self.context.pages[0] if self.context.pages else self.context.new_page()
        )
        self.page.set_default_timeout(30_000)
        # User handles any CAPTCHA; never auto-solve it.
        return StudioDriver(self.page)

    def __exit__(self, *args: Any) -> None:
        self.context.close()
        self.playwright.stop()


class StudioDriver:
    def __init__(self, page: Page):
        self.page = page

    def check_challenge(self) -> None:
        challenge = self.page.locator(
            'iframe[title*="captcha" i], [id="captcha-verify-container"]'
        )
        if any(challenge.nth(i).is_visible() for i in range(challenge.count())):
            raise ToolError("CAPTCHA requires the user; no automatic solving")

    def button(self, name: str, scope: Any = None) -> Locator:
        return unique_visible(
            (scope or self.page).get_by_role("button", name=name, exact=True), name
        )

    def verify_account(self, expected: str) -> None:
        self.page.goto("https://www.tiktok.com/", wait_until="domcontentloaded")
        self.check_challenge()
        # This is the logged-in navigation Profile link, not a profile page URL
        # or links to other creators in the feed.
        deadline = time.monotonic() + 30
        href = ""
        while time.monotonic() < deadline:
            profile = self.page.locator(
                'a[data-e2e="profile-icon"], a[data-e2e="nav-profile"]'
            ).or_(self.page.get_by_role("link", name="Profile", exact=True))
            try:
                link = unique_visible(profile, "logged-in Profile link")
                href = link.get_attribute("href") or ""
                break
            except ToolError:
                self.check_challenge()
                self.page.wait_for_timeout(500)
        if not href:
            raise ToolError(
                "Cannot verify logged-in username. Run login and use an English TikTok interface"
            )
        actual = urlparse(href).path.rstrip("/").removeprefix("/@")
        if actual.lower() != expected.lower():
            raise ToolError(
                f"Wrong TikTok account: expected @{expected}, found @{actual}"
            )

    def matching_links(self, account: str, caption: str) -> list[Locator]:
        links = self.page.locator(f'a[href*="/@{account}/video/"]')
        return [
            links.nth(i)
            for i in range(links.count())
            if normal(links.nth(i).inner_text()) == normal(caption)
        ]

    def baseline(self, account: str, caption: str) -> list[str]:
        self.page.goto(CONTENT_URL, wait_until="domcontentloaded")
        self.page.get_by_text(re.compile(r"^Posts\s*\d*$")).first.wait_for(
            state="visible", timeout=60_000
        )
        self.filter_caption(caption)
        return [
            link.get_attribute("href") or ""
            for link in self.matching_links(account, caption)
        ]

    def filter_caption(self, caption: str) -> None:
        search = self.page.get_by_placeholder("Search for post description", exact=True)
        if search.count():
            search.fill(caption)
            search.press("Enter")
            self.page.wait_for_timeout(2000)

    def prepare(
        self, item: dict[str, Any], policy: str, check_timeout: int
    ) -> dict[str, Any]:
        self.page.goto(UPLOAD_URL, wait_until="domcontentloaded")
        self.check_challenge()
        picker = self.page.locator('input[type="file"]').first
        picker.wait_for(state="attached", timeout=60_000)
        # Exactly one file, irrespective of Studio's batch upload capability.
        picker.set_input_files(item["source"])
        self.page.get_by_text(re.compile(r"^Uploaded\s*[（(]")).first.wait_for(
            state="visible", timeout=180_000
        )
        description = unique_visible(
            self.page.locator(config.selectors.upload.description), "caption"
        )
        description.fill(item["caption"])
        if normal(description.inner_text()) != normal(item["caption"]):
            raise ToolError("Caption did not update")
        product = self.add_product(item.get("product_id"), policy)
        self.enable_ai()
        self.set_schedule(item.get("scheduled_at"))
        self.wait_checks(check_timeout)
        self.audit(item, product)
        return product

    def product_dialog(self) -> Locator:
        heading = self.page.get_by_text("Add product links", exact=True)
        return unique_visible(
            heading.locator(
                "xpath=ancestor::*[.//input[@placeholder='Search products'] and .//table][1]"
            ),
            "product search dialog",
        )

    def add_product(self, product_id: str | None, policy: str) -> dict[str, Any]:
        if policy == "none":
            return {"status": "not_requested", "product_id": None}
        if not product_id or not product_id.isdigit():
            raise ToolError("Missing product ID")
        self.button("Add").click()
        # Link type defaults to Products. Never choose another link type.
        self.page.get_by_text("Products", exact=True).first.wait_for(state="visible")
        self.button("Next").click()
        search = self.page.get_by_placeholder("Search products", exact=True)
        search.wait_for(state="visible")
        search.fill(product_id)
        search.press("Enter")
        dialog = self.product_dialog()
        deadline = time.monotonic() + 45
        empty_since: float | None = None
        row: Locator | None = None
        while time.monotonic() < deadline:
            self.check_challenge()
            matches = dialog.locator("tr").filter(
                has=self.page.get_by_text(product_id, exact=True)
            )
            if matches.count() == 1 and matches.is_visible():
                row = matches
                break
            busy = dialog.locator(
                '[role="progressbar"], [aria-busy="true"], [class*="loading" i], [class*="spinner" i]'
            )
            loading = any(busy.nth(i).is_visible() for i in range(busy.count()))
            data_rows = dialog.locator("tr").filter(has=self.page.locator("td"))
            empty = (
                not loading
                and data_rows.count() == 0
                and search.input_value() == product_id
            )
            empty_since = (empty_since or time.monotonic()) if empty else None
            # A blank table during a request is not a completed no-result response.
            if empty_since and time.monotonic() - empty_since >= 30:
                if policy == "if-available":
                    self.button("Cancel", dialog).click()
                    return {"status": "not_found", "product_id": product_id}
                raise ToolError(f"No exact product result for {product_id}")
            self.page.wait_for_timeout(1000)
        if row is None:
            raise ToolError(
                "Product search did not settle; refusing to treat timeout as no result"
            )
        self.check_product_available(row)
        radio = row.get_by_role("radio")
        unique_visible(radio, "product radio").check()
        if not radio.is_checked():
            raise ToolError("Product selection not checked")
        self.button("Next", dialog).click()
        name_field = self.page.get_by_role("textbox", name="Product name", exact=True)
        if not name_field.count():
            name_field = self.page.locator('input[placeholder="Product name"]')
        name_field.wait_for(state="visible")
        default_name = name_field.input_value()
        if not default_name.strip():
            raise ToolError("Default product display name is empty")
        # Preserve TikTok's default (possibly truncated) anchor title.
        add_dialog = name_field.locator(
            "xpath=ancestor::*[.//button[normalize-space(.)='Add']][1]"
        )
        self.button("Add", unique_visible(add_dialog, "product name dialog")).click()
        name_field.wait_for(state="hidden")
        self.page.get_by_text(default_name, exact=True).first.wait_for(state="visible")
        return {"status": "attached", "product_id": product_id, "name": default_name}

    @staticmethod
    def check_product_available(row: Locator) -> None:
        text = normal(row.inner_text())
        if re.search(r"\b(Inactive|Out of stock|Unavailable)\b", text, re.I):
            raise ToolError(
                "Exact product is unavailable; refusing a different product"
            )

    def enable_ai(self) -> None:
        label = self.page.get_by_text("AI-generated content", exact=True)
        if not label.count() or not label.first.is_visible():
            more = self.page.get_by_text("Show more", exact=True)
            unique_visible(more, "Show more").click()
        label.wait_for(state="visible")
        # Restrict lookup to the smallest row containing the AI label and a switch.
        # Audience control is a separate row and can never be selected here.
        row = label.locator(
            "xpath=ancestor::*[.//*[@role='switch' or @role='checkbox' or @type='checkbox' or @aria-checked]][1]"
        )
        if row.count():
            control = unique_visible(
                row.locator(
                    '[role="switch"], [role="checkbox"], input[type="checkbox"], button[aria-checked]'
                ),
                "AI switch",
            )
            checked = (
                control.is_checked()
                if control.get_attribute("type") == "checkbox"
                else control.get_attribute("aria-checked") == "true"
            )
            if not checked:
                control.click()
        else:
            # Some Studio builds omit switch semantics. Only the AI label's own
            # immediate row is eligible, and preview confirmation is mandatory.
            row = label.locator("..")
            control = unique_visible(
                row.locator('[class*="Switch"], [class*="switch"]'), "AI switch"
            )
            preview = self.page.get_by_text(
                "Creator labeled as AI-generated", exact=False
            )
            if not preview.count() or not preview.first.is_visible():
                control.click()
        notice = self.page.get_by_text("Labeling AI-generated content", exact=True)
        if notice.count() and notice.first.is_visible():
            self.button("Turn on").click()
        self.page.get_by_text(
            "Creator labeled as AI-generated", exact=False
        ).first.wait_for(state="visible")

    def input_with_value(self, pattern: str) -> Locator:
        inputs = self.page.locator("input")
        matches = [
            inputs.nth(i)
            for i in range(inputs.count())
            if inputs.nth(i).is_visible()
            and re.fullmatch(pattern, inputs.nth(i).input_value())
        ]
        if len(matches) != 1:
            raise ToolError("Cannot identify schedule input uniquely")
        return matches[0]

    def set_schedule(self, scheduled_at: str | None) -> None:
        if scheduled_at is None:
            self.page.get_by_role("radio", name="Now", exact=True).check()
            return
        validate_time(scheduled_at)
        when = parse_time(scheduled_at)
        self.page.get_by_role("radio", name="Schedule", exact=True).check()
        date = self.input_with_value(r"\d{4}-\d{2}-\d{2}")
        target = when.strftime("%Y-%m-%d")
        if date.input_value() != target:
            date.click()
            current = datetime.strptime(date.input_value(), "%Y-%m-%d")
            if (current.year, current.month) != (when.year, when.month):
                # No guessed calendar arrows or wrong-year selection.
                next_month = self.page.get_by_role(
                    "button", name=re.compile(r"^Next month$", re.I)
                )
                unique_visible(next_month, "Next month").click()
            day = self.page.locator('[class*="days-wrapper"] [class*="valid"]').filter(
                has_text=re.compile(rf"^{when.day}$")
            )
            unique_visible(day, "scheduled calendar day").click()
            if date.input_value() != target:
                raise ToolError("Calendar did not select the exact date")
        clock = self.input_with_value(r"\d{2}:\d{2}")
        clock.click()
        hour = self.page.locator(config.selectors.schedule.timepicker_hours).filter(
            has_text=re.compile(rf"^{when.hour:02d}$")
        )
        minute = self.page.locator(config.selectors.schedule.timepicker_minutes).filter(
            has_text=re.compile(rf"^{when.minute:02d}$")
        )
        # Select by value, scroll into view, and wait for the picker animation.
        for option in (hour, minute):
            chosen = (
                unique_visible(option, "time picker option")
                if option.count() == 1 and option.is_visible()
                else option
            )
            if chosen.count() != 1:
                raise ToolError("Time picker selectors changed; refusing guessed time")
            chosen.scroll_into_view_if_needed()
            chosen.click()
            self.page.wait_for_timeout(700)
        clock.click()
        if clock.input_value() != when.strftime("%H:%M"):
            raise ToolError("Time picker did not select the exact time")

    def wait_checks(self, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check_challenge()
            body = normal(self.page.locator("body").inner_text())
            if re.search(
                r"Checking in progress|Checking your|Running checks", body, re.I
            ):
                self.page.wait_for_timeout(2000)
                continue
            issues = body.replace("No issues found", "")
            if re.search(
                r"Copyright issue|Issues found|Not eligible|Violations found",
                issues,
                re.I,
            ):
                raise ToolError("TikTok reported a content/copyright issue")
            # Music and content check must both finish. One success label is
            # insufficient while the other check is initializing or disabled.
            if body.count("No issues found") >= 2:
                return
            self.page.wait_for_timeout(2000)
        raise ToolError("TikTok checks still pending; no publish click was attempted")

    def audit(self, item: dict[str, Any], product: dict[str, Any]) -> None:
        description = unique_visible(
            self.page.locator(config.selectors.upload.description), "caption"
        )
        if normal(description.inner_text()) != normal(item["caption"]):
            raise ToolError("Caption changed before submission")
        self.page.get_by_text(
            "Creator labeled as AI-generated", exact=False
        ).first.wait_for(state="visible")
        if product["status"] == "attached":
            self.page.get_by_text(product["name"], exact=True).first.wait_for(
                state="visible"
            )
        if item.get("scheduled_at"):
            validate_time(item["scheduled_at"])
            when = parse_time(item["scheduled_at"])
            if not self.page.get_by_role(
                "radio", name="Schedule", exact=True
            ).is_checked():
                raise ToolError("Schedule mode was lost")
            if self.input_with_value(r"\d{2}:\d{2}").input_value() != when.strftime(
                "%H:%M"
            ):
                raise ToolError("Scheduled time changed")
            if self.input_with_value(
                r"\d{4}-\d{2}-\d{2}"
            ).input_value() != when.strftime("%Y-%m-%d"):
                raise ToolError("Scheduled date changed")
        elif not self.page.get_by_role("radio", name="Now", exact=True).is_checked():
            raise ToolError("Post-now mode was lost")

    def submit(self, item: dict[str, Any]) -> None:
        self.button("Schedule" if item.get("scheduled_at") else "Post").click()
        # Even if checks reappear after our audit, never click the ambiguous
        # "Post now" confirmation. Caller records an unverified submission.
        self.page.wait_for_timeout(1500)
        warning = self.page.get_by_text("Continue to post?", exact=True)
        if warning.count() and warning.first.is_visible():
            self.button("Cancel").click()
            raise ToolError(
                "Unexpected Continue to post warning cancelled; reconcile before retry"
            )

    def verify_result(
        self, account: str, item: dict[str, Any], baseline: list[str]
    ) -> dict[str, Any]:
        self.page.wait_for_url(re.compile(r"/tiktokstudio/content"), timeout=60_000)
        self.filter_caption(item["caption"])
        return self.find_result(account, item, baseline)

    def find_result(
        self, account: str, item: dict[str, Any], baseline: list[str]
    ) -> dict[str, Any]:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            candidates = [
                link
                for link in self.matching_links(account, item["caption"])
                if (link.get_attribute("href") or "") not in baseline
            ]
            if len(candidates) == 1:
                link = candidates[0]
                href = link.get_attribute("href") or ""
                row = link.locator(
                    "xpath=ancestor::*[.//button and count(.//a[contains(@href,'/video/')])=1][1]"
                )
                row_text = normal(row.inner_text())
                if item.get("scheduled_at"):
                    when = parse_time(item["scheduled_at"])
                    day = f"{when.strftime('%b')} {when.day},"
                    hour = when.hour % 12 or 12
                    clock = (
                        f"{hour}:{when.minute:02d} {'AM' if when.hour < 12 else 'PM'}"
                    )
                    if (
                        day not in row_text
                        or clock not in row_text
                        or "GMT+7" not in row_text
                    ):
                        raise ToolError(
                            "New post exists but scheduled date/time is not verified"
                        )
                elif "GMT+7" in row_text:
                    raise ToolError("Expected immediate post, found a scheduled item")
                return {
                    "status": "scheduled" if item.get("scheduled_at") else "published",
                    "post_url": href
                    if href.startswith("https://")
                    else f"https://www.tiktok.com{href}",
                    "scheduled_at": item.get("scheduled_at"),
                    "row_text": row_text,
                }
            if len(candidates) > 1:
                raise ToolError("Multiple new matching posts; refusing to choose one")
            self.page.wait_for_timeout(1000)
        raise ToolError("No unique new post verified; do not submit this video again")

    def reconcile(
        self, account: str, item: dict[str, Any], baseline: list[str]
    ) -> dict[str, Any]:
        self.page.goto(CONTENT_URL, wait_until="domcontentloaded")
        self.page.get_by_text(re.compile(r"^Posts\s*\d*$")).first.wait_for(
            state="visible", timeout=60_000
        )
        self.filter_caption(item["caption"])
        return self.find_result(account, item, baseline)
