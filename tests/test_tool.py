import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from freezegun import freeze_time

from tiktok_uploader.tool.cli import main
from tiktok_uploader.tool.plan import ToolError, make_plan, parse_time, read_plan
from tiktok_uploader.tool.state import Ledger, move_verified, read_records
from tiktok_uploader.tool.workflow import reconcile_item, run_item


@pytest.fixture(autouse=True)
def fixed_clock():
    with freeze_time("2026-11-08T00:00:00Z"):
        yield


@pytest.fixture
def plan(tmp_path):
    video = tmp_path / "1731234556640856114_clip.mp4"
    video.write_bytes(b"test video bytes")
    return make_plan(
        [str(video)],
        "creator",
        ["Caption 🖤"],
        start="2026-11-08T08:00:00+07:00",
        done_dir=str(tmp_path / "DONE"),
    )


class FakeDriver:
    def __init__(self, error=None):
        self.submissions = 0
        self.error = error

    def baseline(self, *args):
        return ["https://www.tiktok.com/@creator/video/old"]

    def prepare(self, *args):
        if self.error == "prepare":
            raise ToolError("Product search not settled")
        return {
            "status": "attached",
            "product_id": "1731234556640856114",
            "name": "Default",
        }

    def audit(self, *args):
        pass

    def submit(self, *args):
        self.submissions += 1
        if self.error == "submit":
            raise TimeoutError()

    def verify_result(self, account, item, baseline):
        if self.error == "verify":
            raise ToolError("No unique new post")
        return {
            "status": "scheduled",
            "post_url": "https://www.tiktok.com/@creator/video/new",
            "scheduled_at": item["scheduled_at"],
        }

    def reconcile(self, account, item, baseline):
        return {
            "status": "scheduled",
            "post_url": "https://www.tiktok.com/@creator/video/new",
            "scheduled_at": item["scheduled_at"],
        }


def test_plan_exact_ids_separate_files_and_times(tmp_path):
    files = []
    for i in range(5):
        path = tmp_path / f"173123455664085611{i}_video.mp4"
        path.write_bytes(bytes([i]))
        files.append(str(path))
    data = make_plan(
        files,
        "@creator",
        [f"caption {i}" for i in range(5)],
        start="2026-11-08T08:00:00+07:00",
    )
    assert len(data["items"]) == 5
    assert [
        datetime.fromisoformat(x["scheduled_at"]).strftime("%H:%M")
        for x in data["items"]
    ] == ["08:00", "08:30", "09:00", "09:30", "10:00"]
    assert data["items"][0]["product_id"] == "1731234556640856110"
    assert all(x["ai_label"] for x in data["items"])


@pytest.mark.parametrize(
    "value", ["2026-11-08T08:01:00+07:00", "2026-11-08T08:00:00", "bad"]
)
def test_schedule_never_silently_rounds(value):
    with pytest.raises(ToolError):
        parse_time(value)


def test_duplicate_content_rejected(tmp_path):
    a, b = tmp_path / "123_a.mp4", tmp_path / "456_b.mp4"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    with pytest.raises(ToolError, match="Duplicate"):
        make_plan([str(a), str(b)], "creator", ["a", "b"])


def test_plan_rejects_tampered_ai_or_key(tmp_path, plan):
    file = tmp_path / "plan.json"
    plan["items"][0]["ai_label"] = False
    file.write_text(json.dumps(plan))
    with pytest.raises(ToolError, match="AI"):
        read_plan(file)


def test_plan_rejects_product_id_changed_to_another_product(tmp_path, plan):
    file = tmp_path / "plan.json"
    plan["items"][0]["product_id"] = "1731234556640856115"
    file.write_text(json.dumps(plan))
    with pytest.raises(ToolError, match="filename"):
        read_plan(file)


@pytest.mark.parametrize("error", ["submit", "verify"])
def test_ambiguous_submission_never_retried_or_moved(tmp_path, plan, error):
    driver = FakeDriver(error)
    item = plan["items"][0]
    with Ledger(tmp_path / "state") as ledger:
        with pytest.raises((TimeoutError, ToolError)):
            run_item(driver, ledger, plan, item, 1)
        assert ledger.get(item["key"])["status"] == "unverified"
        with pytest.raises(ToolError, match="reconciliation"):
            run_item(driver, ledger, plan, item, 1)
        assert driver.submissions == 1
        assert Path(item["source"]).exists()
        assert not Path(item["destination"]).exists()
        record = reconcile_item(driver, ledger, plan, item)
        assert record["status"] == "scheduled"
        assert Path(item["destination"]).read_bytes() == b"test video bytes"
        assert not Path(item["source"]).exists()
        assert driver.submissions == 1


def test_pre_submit_failure_can_retry_without_publication(tmp_path, plan):
    driver = FakeDriver("prepare")
    item = plan["items"][0]
    with Ledger(tmp_path / "state") as ledger:
        with pytest.raises(ToolError):
            run_item(driver, ledger, plan, item, 1)
        assert ledger.get(item["key"])["status"] == "failed_before_submit"
        assert driver.submissions == 0
        driver.error = None
        run_item(driver, ledger, plan, item, 1)
        run_item(driver, ledger, plan, item, 1)
        assert driver.submissions == 1


def test_file_change_and_destination_collision_never_reposts(tmp_path, plan):
    driver, item = FakeDriver(), plan["items"][0]
    Path(item["source"]).write_bytes(b"changed")
    with Ledger(tmp_path / "state") as ledger:
        with pytest.raises(ToolError, match="changed"):
            run_item(driver, ledger, plan, item, 1)
        assert driver.submissions == 0
        Path(item["source"]).write_bytes(b"test video bytes")
        target = Path(item["destination"])
        target.parent.mkdir()
        target.write_bytes(b"unrelated data")
        with pytest.raises(ToolError, match="overwrite"):
            run_item(driver, ledger, plan, item, 1)
        assert ledger.get(item["key"])["status"] == "scheduled"
        with pytest.raises(ToolError):
            run_item(driver, ledger, plan, item, 1)
        assert driver.submissions == 1
        assert target.read_bytes() == b"unrelated data"
        assert Path(item["source"]).exists()


def test_move_requires_verified_url(plan):
    with pytest.raises(ToolError, match="verified"):
        move_verified(plan["items"][0], {"status": "unverified"})


def test_exclusive_ledger_lock(tmp_path):
    with Ledger(tmp_path) as ledger:
        ledger.put("one", status="preparing")
        assert read_records(tmp_path)[0]["status"] == "preparing"
        with pytest.raises(ToolError, match="Another"):
            Ledger(tmp_path)


def test_existing_identical_done_file_is_not_claimed_by_a_new_move(tmp_path, plan):
    item = plan["items"][0]
    target = Path(item["destination"])
    target.parent.mkdir()
    target.write_bytes(Path(item["source"]).read_bytes())
    with Ledger(tmp_path / "state") as ledger:
        with pytest.raises(ToolError, match="overwrite"):
            run_item(FakeDriver(), ledger, plan, item, 1)
        assert ledger.get(item["key"])["status"] == "scheduled"
        assert "move_started" not in ledger.get(item["key"])
        assert Path(item["source"]).exists()


def test_run_without_submit_never_opens_browser(tmp_path, plan, monkeypatch, capsys):
    file = tmp_path / "plan.json"
    file.write_text(json.dumps(plan))
    monkeypatch.setattr("sys.argv", ["tiktok-tool", "run", str(file)])
    monkeypatch.setattr(
        "tiktok_uploader.tool.cli.StudioSession",
        lambda *a: pytest.fail("Browser must not open"),
    )
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["publishing"] is False


def test_launcher_resolves_symlink_and_project_path_with_spaces(tmp_path):
    project = tmp_path / "repo with spaces"
    script = project / "skills/tiktok-product-link-post/scripts/tiktok_tool.sh"
    script.parent.mkdir(parents=True)
    original = (
        Path(__file__).resolve().parents[1]
        / "skills/tiktok-product-link-post/scripts/tiktok_tool.sh"
    )
    shutil.copy2(original, script)
    python = project / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    python.chmod(0o755)
    link = tmp_path / "tiktok-tool"
    link.symlink_to(script)
    environment = dict(os.environ)
    environment.pop("TIKTOK_TOOL_PROJECT", None)
    result = subprocess.run(
        [str(link), "--help"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["-m", "tiktok_uploader.tool.cli", "--help"]
