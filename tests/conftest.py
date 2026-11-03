"""Shared fixtures: small, synthetic archives covering every record kind."""

from __future__ import annotations

import gzip

import pytest

from sy4py.encoder import encode_archive
from sy4py.model import (
    Frame,
    HTTPRequest,
    HTTPResponse,
    HTTPSession,
    Record,
    TCPSession,
    UDPSession,
)


def make_http_record(
    index: int = 1,
    *,
    method: str = "POST",
    url: str = "https://api.example.com/v1/login?token=secret&page=2",
    status: str = "200",
    request_body: bytes = b'{"user":"alice"}',
    response_body: bytes = b'{"ok":true}',
    response_header=None,
) -> Record:
    return Record(
        index=index,
        theology=1000 + index,
        ico="icon",
        user_name="alice",
        note="login flow",
        http=HTTPSession(
            request=HTTPRequest(
                method=method,
                url=url,
                client_ip="127.0.0.1:50000",
                time="10:00:00:001",
                process_name="demo.exe",
                proto="HTTP/1.1",
                header={
                    "Host": ["api.example.com"],
                    "Cookie": ["sid=abcdef"],
                    "Authorization": ["Bearer topsecret"],
                    "Content-Type": ["application/json"],
                },
                body=request_body,
                body_length=len(request_body),
            ),
            response=HTTPResponse(
                time="10:00:00:120",
                code=status,
                state="OK" if status == "200" else "Fail",
                type="application/json",
                length=len(response_body),
                proto="HTTP/1.1",
                header=response_header
                or {"Content-Type": ["application/json"], "Set-Cookie": ["sid=1"]},
                body=response_body,
                server_ip="10.0.0.1:443",
                body_length=len(response_body),
            ),
        ),
    )


def make_websocket_record(index: int = 2) -> Record:
    record = make_http_record(
        index,
        method="GET",
        url="wss://ws.example.com/socket",
        status="101",
        request_body=b"",
        response_body=b"",
    )
    record.http.is_websocket = True
    record.note = "websocket session"
    record.http.streams = [
        Frame(key=1, message_id=1, is_send=False, time="10:01:00:001", body=b"hello"),
        Frame(
            key=2,
            message_id=2,
            is_send=True,
            time="10:01:00:100",
            body=b'{"ping":1}',
        ),
    ]
    record.http.stream_keys = [1, 2]
    return record


def make_tcp_record(index: int = 3) -> Record:
    return Record(
        index=index,
        theology=2000 + index,
        ico="icon",
        client_ip="127.0.0.1:50001",
        process="agent.exe",
        tcp=TCPSession(
            method="CONNECT",
            remote_address="10.0.0.2:443",
            host="tcp.example.com",
            time="10:02:00:000",
            streams=[Frame(key=1, message_id=1, is_send=True, body=b"ping")],
            stream_keys=[1],
        ),
    )


def make_udp_record(index: int = 4) -> Record:
    return Record(
        index=index,
        theology=3000 + index,
        ico="icon",
        client_ip="127.0.0.1:50002",
        process="dns.exe",
        udp=UDPSession(
            method="UDP",
            remote_address="8.8.8.8:53",
            time="10:03:00:000",
            streams=[Frame(key=1, message_id=1, is_send=True, body=b"\x00\x01")],
            stream_keys=[1],
        ),
    )


def make_records() -> list:
    return [
        make_http_record(1),
        make_websocket_record(2),
        make_tcp_record(3),
        make_udp_record(4),
    ]


@pytest.fixture()
def records() -> list:
    return make_records()


@pytest.fixture()
def archive_bytes(records) -> bytes:
    return encode_archive(records, compress=False)


@pytest.fixture()
def compressed_bytes(records) -> bytes:
    return encode_archive(records, compress=True)


@pytest.fixture()
def gzip_http_record() -> Record:
    payload = b'{"compressed":true,"items":[1,2,3]}'
    return make_http_record(
        index=1,
        method="GET",
        url="https://api.example.com/v1/list",
        request_body=b"",
        response_body=gzip.compress(payload),
        response_header={
            "Content-Type": ["application/json"],
            "Content-Encoding": ["gzip"],
        },
    )


@pytest.fixture()
def sample_dir():
    import os

    path = os.environ.get("SY4_SAMPLES")
    return path
