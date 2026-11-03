"""Run the CLI without installing anything.

Supported invocations::

    python scripts/sy4py ...      # directory as a script (no install needed)
    python -m sy4py ...           # installed package, or PYTHONPATH=scripts
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):  # `python scripts/sy4py`
    package_dir = Path(__file__).resolve().parent
    # Running a directory puts the package itself on sys.path, which would let
    # its modules shadow third-party names (e.g. ``brotli``'s ``_brotli``).
    cleaned = []
    for entry in sys.path:
        try:
            resolved = Path(entry or os.getcwd()).resolve()
        except OSError:
            cleaned.append(entry)
            continue
        if resolved != package_dir:
            cleaned.append(entry)
    sys.path[:] = cleaned
    sys.path.insert(0, str(package_dir.parent))
    from sy4py.cli import main
else:  # `python -m sy4py`
    from .cli import main

if __name__ == "__main__":
    sys.exit(main())
