"""
Workspace snapshotting for the FinLegal-Harness evolution loop.

Captures the harness state (agents, commands, hooks, rules, skills, scripts)
before each iteration so changes are auditable and reversible.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

# Subdirectories of ECC_harness_v3_txt to capture.
# data/ is excluded — too big and not part of θ.
HARNESS_COMPONENTS = (
    "agents_insu",
    "commands",
    "hooks",
    "rules",
    "scripts",
    "skills",
)

ROOT_FILES = (
    "CLAUDE.md",
    "contract-parser.md",
    "contract-parser_v2.md",
    "legal-validator_v2.md",
    "validate_v2.md",
)


def snapshot_workspace(harness_dir: Path, dest_dir: Path) -> dict:
    """Copy current harness state to dest_dir. Returns a manifest dict."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "snapshot_time": datetime.now().isoformat(timespec="seconds"),
        "source": str(harness_dir),
        "components": [],
        "files": [],
    }

    for sub in HARNESS_COMPONENTS:
        src = harness_dir / sub
        if not src.exists():
            continue
        dst = dest_dir / sub
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        n_files = sum(1 for _ in dst.rglob("*") if _.is_file())
        manifest["components"].append({"name": sub, "files": n_files})

    for fname in ROOT_FILES:
        src = harness_dir / fname
        if src.exists():
            shutil.copy2(src, dest_dir / fname)
            manifest["files"].append(fname)

    (dest_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    m = snapshot_workspace(src, dst)
    print(json.dumps(m, ensure_ascii=False, indent=2))
