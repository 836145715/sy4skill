#!/usr/bin/env python3
"""Package the skill into ``dist/sy4py.skill``.

Only runtime files are included (SKILL.md, LICENSE, references/, scripts/sy4py/);
development files such as tests, CI config and packaging helpers are skipped so the
archive stays a clean, installable skill.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist"
SKILL_NAME = ROOT.name

INCLUDE_FILES = ["SKILL.md", "LICENSE"]
INCLUDE_DIRS = ["references", "scripts"]
EXCLUDE_NAMES = {"__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {Path("scripts/build_skill.py"), Path("scripts/__init__.py")}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def iter_files() -> list:
    files = []
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file():
            files.append(path)
    for name in INCLUDE_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if EXCLUDE_NAMES & set(relative.parts):
                continue
            if relative in EXCLUDE_FILES:
                continue
            if path.suffix in EXCLUDE_SUFFIXES:
                continue
            files.append(path)
    return sorted(set(files))


def build() -> int:
    if not (ROOT / "SKILL.md").is_file():
        print("error: SKILL.md not found in %s" % ROOT, file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / (SKILL_NAME + ".skill")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in iter_files():
            archive.write(path, Path(SKILL_NAME) / path.relative_to(ROOT))
    print("wrote %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
