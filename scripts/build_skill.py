#!/usr/bin/env python3
"""Package ``skills/sy4py`` into ``dist/sy4py.skill`` (a zip archive).

The archive layout matches the skill spec: every file keeps its ``sy4py/``
prefix so the recipient can unzip it directly into a skills directory.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "sy4py"
OUT_DIR = ROOT / "dist"


def build() -> int:
    skill_md = SKILL_DIR / "SKILL.md"
    if not skill_md.is_file():
        print("error: %s not found" % skill_md, file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / (SKILL_DIR.name + ".skill")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(SKILL_DIR.parent))
    print("wrote %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
