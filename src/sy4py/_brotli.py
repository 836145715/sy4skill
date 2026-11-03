"""Optional Brotli support.

SunnyNetV4 stores ``.sy4`` files Brotli-compressed by default, so this module
is what makes real captures readable.  Either the official ``brotli`` C
extension or ``brotlicffi`` works; if neither is installed, callers get a
clear error instead of a confusing parse failure.
"""

from __future__ import annotations

from typing import Any, Optional

from .errors import Sy4Error

_MODULE: Any = None
_LOADED = False

_MISSING_HINT = (
    "this file is Brotli-compressed but no Brotli backend is installed; "
    "run `pip install brotli` (or `pip install sy4py[brotli]`)"
)


def module() -> Optional[Any]:
    """Return an imported Brotli module, or ``None`` when unavailable."""

    global _MODULE, _LOADED
    if _LOADED:
        return _MODULE
    _LOADED = True
    for name in ("brotli", "brotlicffi"):
        try:
            _MODULE = __import__(name)
        except ImportError:
            continue
        else:
            break
    return _MODULE


def available() -> bool:
    return module() is not None


def decompress(data: bytes) -> bytes:
    mod = module()
    if mod is None:
        raise Sy4Error(_MISSING_HINT)
    return mod.decompress(data)


def compress(data: bytes, quality: int = 6, lgwin: int = 22) -> bytes:
    mod = module()
    if mod is None:
        raise Sy4Error(
            "compressing a .sy4 file needs a Brotli backend; "
            "run `pip install brotli` (or use compress=False)"
        )
    try:
        return mod.compress(data, quality=quality, lgwin=lgwin)
    except TypeError:  # brotlicffi older signatures
        return mod.compress(data)


def missing_hint() -> str:
    return _MISSING_HINT
