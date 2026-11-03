"""Full-text search across URLs, headers, bodies and stream frames."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from .errors import QueryError
from .model import Record

ALL_SCOPES = ("url", "header", "req", "resp", "stream", "note", "error")

_SNIPPET_WINDOW = 40


@dataclass
class SearchOptions:
    scope: str = "all"
    case_insensitive: bool = True
    strip_space: bool = False
    encoding: str = "auto"


@dataclass
class Hit:
    index: int
    field: str
    snippet: str

    def to_dict(self) -> dict:
        return {"index": self.index, "field": self.field, "snippet": self.snippet}


def search(
    records: Iterable[Record], needle: str, options: Optional[SearchOptions] = None
) -> List[Hit]:
    """Return every field/record combination containing ``needle``."""

    options = options or SearchOptions()
    needles = expand_needles(needle, options)
    if not needles:
        raise QueryError("search term is empty")
    scopes = parse_scopes(options.scope)
    hits: List[Hit] = []
    for record in records:
        hits.extend(
            _search_record(record, needles, scopes, options.case_insensitive)
        )
    return hits


def expand_needles(needle: str, options: SearchOptions) -> List[bytes]:
    text = needle
    if options.strip_space:
        text = text.strip().replace(" ", "")
    encoding = (options.encoding or "auto").strip().lower() or "auto"

    found: List[bytes] = []

    def add(value: bytes) -> None:
        if value and value not in found:
            found.append(value)

    if encoding in ("utf8", "utf-8", "text"):
        add(text.encode("utf-8"))
    elif encoding == "hex":
        try:
            add(bytes.fromhex(text.replace(" ", "")))
        except ValueError:
            raise QueryError("invalid hex needle") from None
    elif encoding == "base64":
        try:
            add(base64.b64decode(text, validate=True))
        except (binascii.Error, ValueError):
            raise QueryError("invalid base64 needle") from None
    elif encoding == "auto":
        add(text.encode("utf-8"))
        compact = text.replace(" ", "")
        if compact and len(compact) % 2 == 0:
            try:
                add(bytes.fromhex(compact))
            except ValueError:
                pass
        try:
            add(base64.b64decode(text, validate=True))
        except (binascii.Error, ValueError):
            pass
    else:
        raise QueryError("unknown encoding %r" % options.encoding)
    return found


def parse_scopes(scope: str) -> Dict[str, bool]:
    text = (scope or "").strip()
    if not text or text == "all":
        return {name: True for name in ALL_SCOPES}
    scopes: Dict[str, bool] = {}
    for part in text.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name == "body":
            scopes["req"] = True
            scopes["resp"] = True
        else:
            scopes[name] = True
    return scopes


def _search_record(
    record: Record, needles: Sequence[bytes], scopes: Dict[str, bool], ci: bool
) -> List[Hit]:
    hits: List[Hit] = []

    def check(name: str, text: str = "", raw: Optional[bytes] = None) -> None:
        match = _match_field(name, text, raw, needles, ci)
        if match is not None:
            hits.append(Hit(record.index, match.field, match.snippet))

    if scopes.get("url"):
        check("url", record.url)
    if scopes.get("note"):
        check("note", record.note)
    if scopes.get("error"):
        check("error", record.error)
    if scopes.get("header"):
        check("request.header", header_text(record.req_header))
        check("response.header", header_text(record.resp_header))
    if scopes.get("req"):
        check("request.body", raw=record.req_body)
    if scopes.get("resp"):
        check("response.body", raw=record.resp_body)
    if scopes.get("stream"):
        for position, frame in enumerate(record.frames):
            check("stream[%d].body" % position, raw=frame.body)
    return hits


def header_text(header: dict) -> str:
    if not header:
        return ""
    parts = []
    for key, values in header.items():
        for value in values:
            parts.append("%s: %s\n" % (key, value))
    return "".join(parts)


def _match_field(
    name: str,
    text: str,
    raw: Optional[bytes],
    needles: Sequence[bytes],
    ci: bool,
) -> Optional[Hit]:
    haystack = raw if raw is not None else (text or "").encode("utf-8", "replace")
    if not haystack:
        return None
    for needle in needles:
        position = _index_bytes(haystack, needle, ci)
        if position >= 0:
            return Hit(0, name, _snippet_at(haystack, position, len(needle)))
    return None


def _index_bytes(haystack: bytes, needle: bytes, ci: bool) -> int:
    if not needle:
        return -1
    if ci:
        return haystack.lower().find(needle.lower())
    return haystack.find(needle)


def _snippet_at(data: bytes, position: int, needle_length: int) -> str:
    start = max(0, position - _SNIPPET_WINDOW)
    end = min(len(data), position + needle_length + _SNIPPET_WINDOW)
    chunk = bytearray(data[start:end])
    for i, byte in enumerate(chunk):
        if byte < 32 and byte != 9:
            chunk[i] = ord(".")
    snippet = chunk.decode("utf-8", "replace")
    if start > 0:
        snippet = "..." + snippet
    if end < len(data):
        snippet += "..."
    return snippet
