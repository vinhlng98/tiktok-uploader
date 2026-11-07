"""Local HTML contracts, no TikTok login, uploads, or external network."""

import os

import pytest
from freezegun import freeze_time
from playwright.sync_api import sync_playwright

from tiktok_uploader.tool.plan import ToolError
from tiktok_uploader.tool.studio import StudioDriver

pytestmark = pytest.mark.skipif(
    os.environ.get("TIKTOK_TOOL_BROWSER_TESTS") != "1",
    reason="Opt-in local Chromium tests",
)


@pytest.fixture
def driver():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(1000)
        yield StudioDriver(page)
        browser.close()


def test_ai_toggle_is_separate_from_audience_control_and_idempotent(driver):
    driver.page.set_content("""
    <div><span>AI-generated content</span><button role="switch" aria-checked="false"
      onclick="this.setAttribute('aria-checked','true');document.querySelector('#preview').hidden=false">AI switch</button></div>
    <div><span>Audience control</span><button role="switch" aria-checked="false">18+ switch</button></div>
    <div id="preview" hidden>Creator labeled as AI-generated</div>
    """)
    driver.enable_ai()
    driver.enable_ai()
    assert (
        driver.page.get_by_role("switch", name="AI switch").get_attribute(
            "aria-checked"
        )
        == "true"
    )
    assert (
        driver.page.get_by_role("switch", name="18+ switch").get_attribute(
            "aria-checked"
        )
        == "false"
    )


def test_pending_content_check_never_clicks_post(driver):
    driver.page.set_content(
        '<p>No issues found. Content check lite</p><p>Checking in progress.</p><button onclick="window.clicked=true">Schedule</button>'
    )
    with pytest.raises(ToolError, match="pending"):
        driver.wait_checks(1)
    assert driver.page.evaluate("window.clicked || false") is False


def test_both_checks_must_succeed_and_no_issues_is_not_an_error(driver):
    driver.page.set_content(
        "<p>Music: No issues found</p><p>Content: No issues found</p>"
    )
    driver.wait_checks(1)
    driver.page.set_content(
        "<p>Music: No issues found</p><p>Content: waiting to start</p>"
    )
    with pytest.raises(ToolError, match="pending"):
        driver.wait_checks(1)


def test_surprise_post_now_is_cancelled_never_accepted(driver):
    driver.page.set_content("""
    <button onclick="document.querySelector('#warning').hidden=false">Schedule</button>
    <div id="warning" hidden><p>Continue to post?</p>
      <button onclick="window.posted=true">Post now</button>
      <button onclick="document.querySelector('#warning').hidden=true;window.cancelled=true">Cancel</button>
    </div>""")
    with pytest.raises(ToolError, match="cancelled"):
        driver.submit({"scheduled_at": "2026-11-08T08:00:00+07:00"})
    assert driver.page.evaluate("window.cancelled") is True
    assert driver.page.evaluate("window.posted || false") is False


@freeze_time("2026-11-08T00:00:00Z", real_asyncio=True)
def test_schedule_selects_exact_hour_and_minute(driver):
    driver.page.set_content("""
    <label><input type="radio" name="mode">Now</label>
    <label><input type="radio" name="mode">Schedule</label>
    <input id="date" readonly value="2026-11-08"><input id="clock" readonly value="07:30">
    <span class="tiktok-timepicker-left" onclick="document.querySelector('#clock').value='08:30'">08</span>
    <span class="tiktok-timepicker-right" onclick="document.querySelector('#clock').value='08:35'">35</span>
    """)
    driver.set_schedule("2026-11-08T08:35:00+07:00")
    assert driver.page.locator("#clock").input_value() == "08:35"
    assert driver.page.get_by_role("radio", name="Schedule", exact=True).is_checked()


def test_late_product_result_is_waited_and_default_name_preserved(driver):
    driver.page.set_content("""
    <button id="open" onclick="document.querySelector('#type').hidden=false;this.hidden=true">Add</button>
    <div id="type" hidden><span>Products</span><button onclick="this.parentElement.hidden=true;document.querySelector('#searchDialog').hidden=false">Next</button></div>
    <div id="searchDialog" hidden><h2>Add product links</h2>
      <input placeholder="Search products" onkeydown="if(event.key==='Enter')setTimeout(()=>{document.querySelector('#product').hidden=false},500)">
      <table><tr><th>Product ID</th></tr>
      <tr id="product" hidden><td><input type="radio"></td><td>1731234556640856114</td><td>Active</td></tr></table>
      <button onclick="this.parentElement.hidden=true;document.querySelector('#nameDialog').hidden=false">Next</button><button>Cancel</button>
    </div>
    <div id="nameDialog" hidden><label>Product name<input value="Original default title"></label>
      <button onclick="this.parentElement.hidden=true;document.querySelector('#anchor').hidden=false">Add</button><button>Cancel</button></div>
    <div id="anchor" hidden>Original default title</div>
    """)
    product = driver.add_product("1731234556640856114", "required")
    assert product == {
        "status": "attached",
        "product_id": "1731234556640856114",
        "name": "Original default title",
    }
    assert driver.page.locator("#anchor").is_visible()


def test_result_requires_new_url_and_exact_schedule(driver):
    caption = "Caption 🖤"
    driver.page.set_content(
        """<div><a href="/@creator/video/new">Caption 🖤</a><span>Nov 8, 8:30 AM (GMT+7) Saigon</span><button>Actions</button></div>"""
    )
    with pytest.raises(ToolError, match="not verified"):
        driver.find_result(
            "creator",
            {"caption": caption, "scheduled_at": "2026-11-08T08:35:00+07:00"},
            [],
        )
    result = driver.find_result(
        "creator", {"caption": caption, "scheduled_at": "2026-11-08T08:30:00+07:00"}, []
    )
    assert result["status"] == "scheduled"
