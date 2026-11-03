"""Body/header content helpers: text detection, charset guessing, decoding."""

from __future__ import annotations

import gzip
import zlib
from typing import Optional, Tuple

from . import _brotli

#: Encodings tried in order when guessing how to render a body as text.
TEXT_ENCODINGS = ("utf-8", "gb18030")


def looks_text(data: bytes) -> bool:
    """Cheap heuristic: does this byte string look like text, not binary?"""

    if not data:
        return True
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32 or byte == 127)
    return control / len(sample) < 0.05


def decode_text(data: bytes) -> Tuple[str, str]:
    """Decode ``data`` as text, returning ``(text, encoding)``.

    Raises :class:`UnicodeDecodeError` when nothing plausible matches.
    """

    last_error: Optional[UnicodeDecodeError] = None
    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error  # type: ignore[misc]


def decode_text_or_none(data: bytes) -> Optional[str]:
    """Best-effort text decoding; ``None`` means "treat as binary"."""

    if not data or not looks_text(data):
        return None
    try:
        text, _ = decode_text(data)
    except UnicodeDecodeError:
        return None
    return text


def content_encoding(header: dict) -> str:
    """Read ``Content-Encoding`` from a header mapping (case-insensitive)."""

    for key, values in (header or {}).items():
        if key.lower() == "content-encoding" and values:
            return values[0]
    return ""


def content_type(header: dict) -> str:
    for key, values in (header or {}).items():
        if key.lower() == "content-type" and values:
            return values[0]
    return ""


def decompress_body(data: bytes, encoding: str) -> Optional[bytes]:
    """Best-effort decompression for gzip / deflate / br.

    Returns ``None`` when the data is not compressed with a supported codec or
    cannot be decoded.
    """

    encodings = [part.strip().lower() for part in (encoding or "").split(",")]
    encodings = [item for item in encodings if item and item != "identity"]
    if not data or not encodings:
        return None
    result = data
    for name in reversed(encodings):
        decoded = _decompress_once(result, name)
        if decoded is None:
            return None
        result = decoded
    return result


def _decompress_once(data: bytes, name: str) -> Optional[bytes]:
    if name in ("gzip", "x-gzip"):
        try:
            return gzip.decompress(data)
        except OSError:
            try:
                return zlib.decompress(data, 16 + zlib.MAX_WBITS)
            except zlib.error:
                return None
    if name == "deflate":
        for window_bits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompress(data, window_bits)
            except zlib.error:
                continue
        return None
    if name in ("br", "brotli"):
        try:
            return _brotli.decompress(data)
        except Exception:  # noqa: BLE001 - any failure means "not useful"
            return None
    return None


def hexdump(data: bytes, width: int = 16) -> str:
    """Classic ``xxd``-style dump used when a body is not printable."""

    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join("%02x" % byte for byte in chunk)
        hex_part = hex_part.ljust(width * 3 - 1)
        ascii_part = "".join(
            chr(byte) if 32 <= byte <= 126 else "." for byte in chunk
        )
        lines.append("%08x  %s |%s|" % (offset, hex_part, ascii_part))
    return "\n".join(lines) + ("\n" if lines else "")
