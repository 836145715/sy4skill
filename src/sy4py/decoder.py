"""Decode ``.sy4`` archives (raw or Brotli-compressed)."""

from __future__ import annotations

import os
from typing import List, Tuple

from . import _brotli
from .errors import DecodeError
from .model import (
    TYPE_HTTP,
    TYPE_TCP,
    TYPE_UDP,
    Archive,
    Frame,
    HTTPRequest,
    HTTPResponse,
    HTTPSession,
    Record,
    TCPSession,
    UDPSession,
    fill_derived,
)
from .reader import MAX_RECORDS, Reader


def looks_raw(data: bytes) -> bool:
    """Heuristic: does ``data`` start with a plausible plain ``.sy4`` header?"""

    if len(data) < 8:
        return False
    count = int.from_bytes(data[:8], "big")
    if count > MAX_RECORDS:
        return False
    if count == 0:
        return len(data) == 8
    if len(data) < 9:
        return False
    return data[8:9] in (b"1", b"2", b"3")


def _plausible(header_count: int, records: List[Record]) -> bool:
    if header_count < 0 or header_count > MAX_RECORDS:
        return False
    if header_count > 0 and not records:
        return False
    return True


def open_file(path: str) -> Archive:
    """Read and decode a ``.sy4`` file from disk."""

    with open(path, "rb") as handle:
        data = handle.read()
    archive = decode_bytes(data)
    archive.path = path
    return archive


def decode_file(path: str) -> Archive:
    """Alias of :func:`open_file`."""

    return open_file(path)


def decode_bytes(data: bytes) -> Archive:
    """Decode an in-memory ``.sy4`` blob, sniffing Brotli automatically."""

    if not data:
        raise DecodeError("file is empty")
    if looks_raw(data):
        header_count, records = _decode_stream(data)
        return Archive(header_count=header_count, records=records, compressed=False)

    if _brotli.available():
        try:
            raw = _brotli.decompress(data)
        except Exception:  # noqa: BLE001 - any backend failure means "not brotli"
            raw = None
        if raw is not None:
            try:
                header_count, records = _decode_stream(raw)
            except DecodeError:
                pass
            else:
                if _plausible(header_count, records):
                    return Archive(
                        header_count=header_count, records=records, compressed=True
                    )
    else:
        raise DecodeError(_brotli.missing_hint())

    header_count, records = _decode_stream(data)
    return Archive(header_count=header_count, records=records, compressed=False)


def decode(data: bytes) -> Archive:
    """Alias of :func:`decode_bytes`."""

    return decode_bytes(data)


def _decode_stream(data: bytes) -> Tuple[int, List[Record]]:
    reader = Reader(data)
    try:
        count = reader.read_int()
    except DecodeError as exc:
        raise DecodeError("failed to read record count: %s" % exc) from None
    if count < 0 or count > MAX_RECORDS:
        raise DecodeError("insane record count: %d" % count)

    records: List[Record] = []
    index = 0
    while not reader.eof():
        try:
            record_type = reader.read_type()
        except DecodeError:
            raise
        index += 1
        try:
            record = _read_record(reader, record_type)
        except DecodeError as exc:
            raise DecodeError(
                "record %d (type=%r) at offset %d: %s"
                % (index, record_type, reader.offset, exc)
            ) from None
        record.index = index
        fill_derived(record)
        records.append(record)
    return count, records


def _read_record(reader: Reader, record_type: str) -> Record:
    if record_type == TYPE_HTTP:
        return _read_http(reader)
    if record_type == TYPE_TCP:
        return _read_tcp(reader)
    if record_type == TYPE_UDP:
        return _read_udp(reader)
    raise DecodeError("unknown record type %r" % record_type)


def _read_http(reader: Reader) -> Record:
    record = Record(http=HTTPSession())
    session = record.http
    record.theology = reader.read_int()
    record.ico = reader.read_string()
    session.request = _read_http_request(reader)
    session.response = _read_http_response(reader)
    record.error = reader.read_string()
    session.state = reader.read_int()
    record.rec_length = reader.read_int()
    record.sen_length = reader.read_int()
    record.note = reader.read_string()
    session.streams = _read_ws_frames(reader)
    session.stream_keys = reader.read_int_array()
    session.is_websocket = reader.read_bool()
    session.websocket_disconnect = reader.read_bool()
    record.user_name = reader.read_string()
    return record


def _read_http_request(reader: Reader) -> HTTPRequest:
    request = HTTPRequest()
    request.method = reader.read_string()
    request.url = reader.read_string()
    request.client_ip = reader.read_string()
    request.time = reader.read_string()
    request.process_name = reader.read_string()
    request.proto = reader.read_string()
    request.header = reader.read_header()
    request.body = reader.read_body()
    request.body_length = reader.read_int()
    request.is_max_length = reader.read_bool()
    return request


def _read_http_response(reader: Reader) -> HTTPResponse:
    response = HTTPResponse()
    response.time = reader.read_string()
    response.code = reader.read_string()
    response.state = reader.read_string()
    response.type = reader.read_string()
    response.length = reader.read_int()
    response.proto = reader.read_string()
    response.header = reader.read_header()
    response.body = reader.read_body()
    response.response_type = reader.read_string()
    response.server_ip = reader.read_string()
    response.body_length = reader.read_int()
    response.is_max_length = reader.read_bool()
    return response


def _read_tcp(reader: Reader) -> Record:
    record = Record(tcp=TCPSession())
    session = record.tcp
    record.theology = reader.read_int()
    session.method = reader.read_string()
    record.ico = reader.read_string()
    record.note = reader.read_string()
    record.client_ip = reader.read_string()
    record.process = reader.read_string()
    session.remote_address = reader.read_string()
    session.host = reader.read_string()
    session.time = reader.read_string()
    record.rec_length = reader.read_int()
    record.sen_length = reader.read_int()
    session.streams = _read_stream_frames(reader)
    session.stream_keys = reader.read_int_array()
    record.user_name = reader.read_string()
    return record


def _read_udp(reader: Reader) -> Record:
    record = Record(udp=UDPSession())
    session = record.udp
    record.theology = reader.read_int()
    session.method = reader.read_string()
    record.ico = reader.read_string()
    record.note = reader.read_string()
    record.client_ip = reader.read_string()
    record.process = reader.read_string()
    session.remote_address = reader.read_string()
    session.time = reader.read_string()
    record.rec_length = reader.read_int()
    record.sen_length = reader.read_int()
    session.streams = _read_stream_frames(reader)
    session.stream_keys = reader.read_int_array()
    record.user_name = reader.read_string()
    return record


def _read_ws_frames(reader: Reader) -> List[Frame]:
    count = reader.read_int()
    if count < 0 or count > MAX_RECORDS:
        raise DecodeError("suspicious websocket frame count %d" % count)
    frames: List[Frame] = []
    for _ in range(count):
        key = reader.read_int()
        frame = Frame(key=key)
        frame.message_id = reader.read_int()
        frame.is_send = reader.read_bool()
        frame.is_active_send = reader.read_bool()
        frame.time = reader.read_string()
        frame.body = reader.read_body()
        frame.websocket_type = reader.read_int()
        frame.is_close = reader.read_bool()
        frames.append(frame)
    return frames


def _read_stream_frames(reader: Reader) -> List[Frame]:
    count = reader.read_int()
    if count < 0 or count > MAX_RECORDS:
        raise DecodeError("suspicious stream frame count %d" % count)
    frames: List[Frame] = []
    for _ in range(count):
        key = reader.read_int()
        frame = Frame(key=key)
        frame.message_id = reader.read_int()
        frame.is_send = reader.read_bool()
        frame.is_active_send = reader.read_bool()
        frame.time = reader.read_string()
        frame.body = reader.read_body()
        frame.is_close = reader.read_bool()
        frame.websocket_type = reader.read_int()
        frames.append(frame)
    return frames


__all__ = [
    "archive_size",
    "decode",
    "decode_bytes",
    "decode_file",
    "looks_raw",
    "open_file",
]


def archive_size(path: str) -> int:
    """Convenience helper: size in bytes of a capture file."""

    return os.path.getsize(path)
