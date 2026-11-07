"""Install this fork's skill; preserve existing UI metadata."""

import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".codex/skills/tiktok-product-link-post",
    )
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    source = project / "skills/tiktok-product-link-post"
    target = args.target.expanduser().resolve()
    (target / "references").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(exist_ok=True)
    previous = target / "SKILL.md"
    backup = target / "references/SKILL.before-tool.md"
    if previous.exists() and not backup.exists():
        shutil.copy2(previous, backup)
    for relative in (
        "SKILL.md",
        "references/manual-studio.md",
        "references/tool.md",
        "scripts/tiktok_tool.sh",
    ):
        original = (
            project / "TOOL.md"
            if relative == "references/tool.md"
            else source / relative
        )
        shutil.copy2(original, target / relative)
    (target / "references/tool-project").write_text(str(project) + "\n")
    (target / "scripts/tiktok_tool.sh").chmod(0o755)
    print(f"Installed skill: {target}")
    print(f"Tool project: {project}")


if __name__ == "__main__":
    main()
