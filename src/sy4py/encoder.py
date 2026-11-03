"""Encode records back into ``.sy4`` (raw or Brotli-compressed).

Used by ``sy4py export`` and by the round-trip tests that guard against field
order mistakes in :mod:`sy4py.decoder`.
"""

from __future__ import annotations

import struct
from typing import Iterable, List

from . import _brotli
from .errors import Sy4Error
from .model import TYPE_HTTP, TYPE_TCP, TYPE_UDP, Frame, Record

_U64 = struct.Struct(">Q")


class _Writer:
    __slots__ = ("_parts",)

    def __init__(self) -> None:
        self._parts: List[bytes] = []

    def raw(self, data: bytes) -> None:
        self._parts.append(data)

    def int(self, value: int) -> None:
        self._parts.append(_U64.pack(value & 0xFFFFFFFFFFFFFFFF))

    def bool(self, value: bool) -> None:
        self._parts.append(b"\x01" if value else b"\x00")

    def string(self, value: str) -> None:
        payload = value.encode("utf-8", "replace")
        self.int(len(payload))
        if payload:
            self._parts.append(payload)

    def body(self, value: bytes) -> None:
        value = value or b""
        self.int(len(value))
        if value:
            self._parts.append(value)

    def header(self, header) -> None:
        header = header or {}
        self.int(len(header))
        for key, values in header.items():
            self.string(key)
            self.int(len(values))
            for item in values:
                self.string(item)

    def int_array(self, values) -> None:
        values = list(values or ())
        self.int(len(values))
        for item in values:
            self.int(item)

    def getvalue(self) -> bytes:
        return b"".join(self._parts)


def encode_records(records: Iterable[Record]) -> bytes:
    """Serialize records into the uncompressed ``.sy4`` byte stream."""

    records = list(records)
    writer = _Writer()
    writer.int(len(records))
    for record in records:
        _write_record(writer, record)
    return writer.getvalue()


def encode_archive(records: Iterable[Record], compress: bool = True) -> bytes:
    """Serialize records, optionally Brotli-compressing the result."""

    payload = encode_records(records)
    if not compress:
        return payload
    return _brotli.compress(payload)


def write_file(path: str, records: Iterable[Record], compress: bool = True) -> int:
    """Write records to ``path``; returns the number of bytes written."""

    payload = encode_archive(records, compress=compress)
    with open(path, "wb") as handle:
        handle.write(payload)
    return len(payload)


def _write_record(writer: _Writer, record: Record) -> None:
    if record.http is not None:
        writer.raw(TYPE_HTTP.encode("ascii"))
        _write_http(writer, record)
    elif record.tcp is not None:
        writer.raw(TYPE_TCP.encode("ascii"))
        _write_tcp(writer, record)
    elif record.udp is not None:
        writer.raw(TYPE_UDP.encode("ascii"))
        _write_udp(writer, record)
    else:
        raise Sy4Error("record #%d has no http/tcp/udp session" % record.index)


def _write_http(writer: _Writer, record: Record) -> None:
    session = record.http
    writer.int(record.theology)
    writer.string(record.ico)
    _write_http_request(writer, session.request)
    _write_http_response(writer, session.response)
    writer.string(record.error)
    writer.int(session.state)
    writer.int(record.rec_length)
    writer.int(record.sen_length)
    writer.string(record.note)
    _write_ws_frames(writer, session.streams)
    writer.int_array(session.stream_keys)
    writer.bool(session.is_websocket)
    writer.bool(session.websocket_disconnect)
    writer.string(record.user_name)


def _write_http_request(writer: _Writer, request) -> None:
    writer.string(request.method)
    writer.string(request.url)
    writer.string(request.client_ip)
    writer.string(request.time)
    writer.string(request.process_name)
    writer.string(request.proto)
    writer.header(request.header)
    writer.body(request.body)
    writer.int(request.body_length)
    writer.bool(request.is_max_length)


def _write_http_response(writer: _Writer, response) -> None:
    writer.string(response.time)
    writer.string(response.code)
    writer.string(response.state)
    writer.string(response.type)
    writer.int(response.length)
    writer.string(response.proto)
    writer.header(response.header)
    writer.body(response.body)
    writer.string(response.response_type)
    writer.string(response.server_ip)
    writer.int(response.body_length)
    writer.bool(response.is_max_length)


def _write_ws_frames(writer: _Writer, frames: List[Frame]) -> None:
    frames = list(frames or ())
    writer.int(len(frames))
    for frame in frames:
        writer.int(frame.key)
        writer.int(frame.message_id)
        writer.bool(frame.is_send)
        writer.bool(frame.is_active_send)
        writer.string(frame.time)
        writer.body(frame.body)
        writer.int(frame.websocket_type)
        writer.bool(frame.is_close)


def _write_tcp(writer: _Writer, record: Record) -> None:
    session = record.tcp
    writer.int(record.theology)
    writer.string(session.method)
    writer.string(record.ico)
    writer.string(record.note)
    writer.string(record.client_ip)
    writer.string(record.process)
    writer.string(session.remote_address)
    writer.string(session.host)
    writer.string(session.time)
    writer.int(record.rec_length)
    writer.int(record.sen_length)
    _write_stream_frames(writer, session.streams)
    writer.int_array(session.stream_keys)
    writer.string(record.user_name)


def _write_udp(writer: _Writer, record: Record) -> None:
    session = record.udp
    writer.int(record.theology)
    writer.string(session.method)
    writer.string(record.ico)
    writer.string(record.note)
    writer.string(record.client_ip)
    writer.string(record.process)
    writer.string(session.remote_address)
    writer.string(session.time)
    writer.int(record.rec_length)
    writer.int(record.sen_length)
    _write_stream_frames(writer, session.streams)
    writer.int_array(session.stream_keys)
    writer.string(record.user_name)


def _write_stream_frames(writer: _Writer, frames: List[Frame]) -> None:
    frames = list(frames or ())
    writer.int(len(frames))
    for frame in frames:
        writer.int(frame.key)
        writer.int(frame.message_id)
        writer.bool(frame.is_send)
        writer.bool(frame.is_active_send)
        writer.string(frame.time)
        writer.body(frame.body)
        writer.bool(frame.is_close)
        writer.int(frame.websocket_type)
