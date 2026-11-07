#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${TIKTOK_TOOL_PROJECT:-}" ]; then
  project=$TIKTOK_TOOL_PROJECT
elif [ -f "$script_dir/../references/tool-project" ]; then
  IFS= read -r project < "$script_dir/../references/tool-project"
else
  project=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
fi
if [ ! -x "$project/.venv/bin/python" ]; then
  echo "Tool chưa cài: chạy uv sync --all-groups trong $project" >&2
  exit 2
fi
export TIKTOK_TOOL_HOME="${TIKTOK_TOOL_HOME:-$HOME/.local/share/tiktok-tool}"
if [ -z "${TIKTOK_BROWSER_EXECUTABLE:-}" ] && [ -x /Applications/CocCoc.app/Contents/MacOS/CocCoc ]; then
  export TIKTOK_BROWSER_EXECUTABLE=/Applications/CocCoc.app/Contents/MacOS/CocCoc
fi
exec "$project/.venv/bin/python" -m tiktok_uploader.tool.cli "$@"
