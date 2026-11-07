# TikTok Tool — verified Studio workflow

This fork adds **`tiktok-tool`**, an opt-in workflow beside the upstream CLI.
The original `tiktok-uploader` command is retained for compatibility; the skill
uses only `tiktok-tool`. Upstream: wkaisertexas/tiktok-uploader at
`1cea92dd4c815dbd5127ee4b3a0a7b6fabbaa5f0` (MIT, original license retained).

## Install and login

Python 3.10+ and `uv`:

```sh
uv sync --all-groups
uv run playwright install chromium
uv run tiktok-tool login --account YOUR_TIKTOK_USERNAME
uv run tiktok-tool doctor --account YOUR_TIKTOK_USERNAME
```

Complete login and any CAPTCHA yourself in the dedicated browser window.
The tool verifies the **logged-in Profile navigation link** before uploading.
It never reads your usual browser's cookie database or imports session tokens
from another app. Profiles and ledger live in `~/.local/share/tiktok-tool` by
default; set `TIKTOK_TOOL_HOME` once to choose another stable private location.
Do not switch state directories between runs: duplicate protection is local.

For Cốc Cốc on macOS, pass a binary path before the subcommand:

```sh
uv run tiktok-tool --browser-executable '/Applications/CocCoc.app/Contents/MacOS/CocCoc' login --account YOUR_TIKTOK_USERNAME
```

This still creates an **isolated profile**, never opens your ordinary profile.
`TIKTOK_BROWSER_EXECUTABLE` is the equivalent environment setting.

## Plan, inspect, run

Supply explicit files, one video per post. A single caption repeats across the
explicit files; repeat `--caption` for per-file captions, or provide a JSON array.
Product IDs remain strings and are extracted from the digits before the first `_`.

```sh
uv run tiktok-tool plan '/absolute/path/1731234556640856114_video.mp4' \
  --account YOUR_TIKTOK_USERNAME \
  --caption 'Một ngày thật nhẹ nhàng 🖤' \
  --start '2026-11-09T10:30:00+07:00' --interval 30 \
  --product-policy required \
  --done-dir '/absolute/path/VIDEO/DONE TIKTOK' --out plans/batch.json

uv run tiktok-tool run plans/batch.json              # offline inspection only
uv run tiktok-tool run plans/batch.json --submit     # real publication
uv run tiktok-tool status
uv run tiktok-tool reconcile plans/batch.json         # read-only TikTok check; may finish a verified file move
```

Dates above are examples: choose a future date. Schedule uses Asia/Ho_Chi_Minh,
five-minute boundaries, 20 minutes–10 days ahead. It never rounds or shifts an
approved time. Each remaining job is revalidated before upload and submission.

Product policy:

- `required`: stop if the exact product cannot be attached.
- `if-available`: permitted only when the user says “if available”; skip only
  after a settled empty table (30 seconds). Timeouts and attachment errors stop.
- `none`: explicit request to publish without a product.

The default product display name is preserved. Review media/product consistency
before creating the plan. The tool validates the exact ID, selection and anchor
title but cannot determine visually whether a garment matches the listing.

## Publication and retry guarantees

- AI label is mandatory and confirmed in preview. Audience control is untouched.
- Content checks are not disabled. Pending/failed checks stop before submission.
- A surprise **Continue to post? / Post now** dialog is cancelled, never accepted.
- Before clicking Schedule/Post, the SQLite ledger commits `submitting`.
- A failed/interrupting submission becomes `unverified`; retries are blocked.
  `reconcile` checks for a unique new URL absent from the pre-upload baseline.
- A scheduled row must match the caption, date, time and GMT+7. Only then is a
  job marked `scheduled`; an upstream generic success toast is insufficient.
- Already verified video bytes for the same account are skipped, even if a
  later plan changes the caption/time. An intentional repost needs a separate
  reviewed workflow; there is no automatic force-retry flag.
- Source moves happen only after verification, refuse overwrite and verify
  SHA-256. A move failure preserves verified publication state, so rerunning
  cannot publish the same video again.
- The process lock prevents concurrent runs sharing a profile/ledger.

Use one stable state directory. Keep profiles, plans, evidence screenshots and
SQLite files private; they are not included in Git. `--submit` is a deliberate
execution flag, not permission to publish beyond the user's requested scope.

## Current limits and validation

Video only, original sound, English Studio, Vietnam timezone. Photo posts and
adding TikTok library sounds remain in the skill's manual UI workflow.
TikTok changes DOM selectors; the adapter stops instead of guessing controls.
Cross-month calendar layouts without an accessible Next month button stop.

Automated tests cover planning, file fingerprints, duplicate prevention,
ambiguous submission handling, moves, and browser behavior on local HTML
fixtures. **These tests do not prove live TikTok compatibility**. Run `doctor`,
then validate one explicitly authorized real post before relying on batch runs.
Creating this tool does not publish a test post automatically.

```sh
uv run pytest
TIKTOK_TOOL_BROWSER_TESTS=1 uv run pytest tests/test_tool_browser.py
```
