"""sy4py — read SunnyNetV4 ``.sy4`` capture files in pure Python.

Quick start::

    from sy4py import open_file

    archive = open_file("capture.sy4")
    print(archive.header_count, len(archive))

    for record in archive:
        if record.status == "200" and "api" in record.host:
            print(record.index, record.method, record.url)
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "Archive",
    "DecodeError",
    "Frame",
    "HTTPRequest",
    "HTTPResponse",
    "HTTPSession",
    "Hit",
    "KIND_HTTP",
    "KIND_TCP",
    "KIND_UDP",
    "KIND_WEBSOCKET",
    "Query",
    "QueryError",
    "Record",
    "SearchOptions",
    "Stats",
    "Sy4Error",
    "TCPSession",
    "UDPSession",
    "UsageError",
    "by_index",
    "by_theology",
    "decode",
    "decode_bytes",
    "decode_file",
    "encode_archive",
    "encode_records",
    "looks_raw",
    "open_file",
    "parse_expr",
    "search",
    "summarize",
    "write_file",
    "__version__",
]

from .decoder import decode, decode_bytes, decode_file, looks_raw, open_file
from .encoder import encode_archive, encode_records, write_file
from .errors import DecodeError, QueryError, Sy4Error, UsageError
from .model import (
    KIND_HTTP,
    KIND_TCP,
    KIND_UDP,
    KIND_WEBSOCKET,
    Archive,
    Frame,
    HTTPRequest,
    HTTPResponse,
    HTTPSession,
    Record,
    TCPSession,
    UDPSession,
)
from .query import Query, by_index, by_theology, parse_expr
from .search import Hit, SearchOptions, search
from .stats import Stats, summarize
