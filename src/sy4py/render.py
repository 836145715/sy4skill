"""Terminal rendering helpers (tables, JSON, previews, hex dumps)."""

from __future__ import annotations

import json
import sys
import unicodedata
from typing import Iterable, List, Optional, Sequence

from .content import decode_text_or_none, hexdump
from .model import Frame, Record

DEFAULT_PREVIEW = 2048


def display_width(text: str) -> int:
    """Terminal width of ``text`` counting CJK/fullwidth glyphs as 2 cells."""

    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def pad(text: str, width: int) -> str:
    missing = width - display_width(text)
    return text + " " * missing if missing > 0 else text


def cut(text: str, width: int) -> str:
    """Truncate to ``width`` display cells, appending an ellipsis."""

    if display_width(text) <= width:
        return text
    out: List[str] = []
    used = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if used + char_width > width - 1:
            break
        out.append(char)
        used += char_width
    return "".join(out) + "…"


def human_bytes(count: int) -> str:
    if count >= 1 << 20:
        return "%.1fMB" % (count / float(1 << 20))
    if count >= 1 << 10:
        return "%.1fKB" % (count / float(1 << 10))
    return "%dB" % count


def frame_direction(frame: Frame) -> str:
    return frame.direction


def preview_bytes(body: bytes, limit: int = 60) -> str:
    if not body:
        return ""
    chunk = body[:limit]
    text = decode_text_or_none(chunk)
    if text is not None:
        return text.replace("\n", "\\n").replace("\r", "\\r")
    return chunk.hex()


def body_field(body: bytes, full: bool = False, limit: int = DEFAULT_PREVIEW):
    """JSON representation of a body: text when printable, otherwise hex."""

    if not body:
        return ""
    chunk = body if full or len(body) <= limit else body[:limit]
    text = decode_text_or_none(chunk)
    if text is not None:
        return text
    return {"encoding": "hex", "data": chunk.hex()}


def record_json(record: Record, full: bool = False) -> dict:
    data = record.to_dict()
    data.pop("streams", None)
    if record.http is not None:
        data["request"]["body"] = body_field(record.http.request.body, full)
        data["response"]["body"] = body_field(record.http.response.body, full)
    frames = record.frames
    if frames:
        data["streams"] = [
            {
                "i": position,
                "key": frame.key,
                "messageId": frame.message_id,
                "dir": frame_direction(frame),
                "time": frame.time,
                "close": frame.is_close,
                "length": len(frame.body),
                "body": body_field(frame.body, full),
            }
            for position, frame in enumerate(frames)
        ]
    return data


def summaries(records: Iterable[Record]) -> List[dict]:
    return [record.to_summary() for record in records]


def format_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [display_width(header) for header in headers]
    for row in rows:
        for position, cell in enumerate(row):
            widths[position] = max(widths[position], display_width(cell))
    lines = [_render_row(headers, widths)]
    lines.extend(_render_row(row, widths) for row in rows)
    return "\n".join(lines)


def _render_row(cells: Sequence[str], widths: Sequence[int]) -> str:
    parts = []
    for position, cell in enumerate(cells):
        if position == len(cells) - 1:
            parts.append(cell)
        else:
            parts.append(pad(cell, widths[position] + 2))
    return "".join(parts).rstrip()


def dump_json(value) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def print_body(body: bytes, full: bool, limit: int = DEFAULT_PREVIEW) -> None:
    if not body:
        print("(empty)")
        return
    if not full and len(body) > limit:
        chunk = body[:limit]
        text = decode_text_or_none(chunk)
        if text is not None:
            print(text)
        else:
            sys.stdout.write(hexdump(chunk))
        print("... truncated, %d bytes total; use --full or `sy4py body`" % len(body))
        return
    text = decode_text_or_none(body)
    if text is not None:
        print(text)
    else:
        sys.stdout.write(hexdump(body))


def header_lines(header: dict) -> Optional[str]:
    if not header:
        return None
    lines: List[str] = []
    for key, values in header.items():
        for value in values:
            lines.append("%s: %s" % (key, value))
    return "\n".join(lines)
