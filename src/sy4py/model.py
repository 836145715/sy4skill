"""Data model for ``.sy4`` records.

The field names are snake_case on purpose; :meth:`Record.to_dict` and friends
emit the camelCase keys used by the reference Go implementation so that JSON
consumers (agents, dashboards) can stay compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlsplit

KIND_HTTP = "http"
KIND_WEBSOCKET = "websocket"
KIND_TCP = "tcp"
KIND_UDP = "udp"

TYPE_HTTP = "1"
TYPE_TCP = "2"
TYPE_UDP = "3"

Header = Dict[str, List[str]]


@dataclass
class Frame:
    """One WebSocket / TCP / UDP data frame."""

    key: int = 0
    message_id: int = 0
    is_send: bool = False
    is_active_send: bool = False
    time: str = ""
    body: bytes = b""
    websocket_type: int = 0
    is_close: bool = False

    @property
    def direction(self) -> str:
        if self.is_close:
            return "close"
        if self.is_active_send:
            return "manual-send"
        return "send" if self.is_send else "recv"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "messageId": self.message_id,
            "isSend": self.is_send,
            "isActiveSend": self.is_active_send,
            "time": self.time,
            "websocketType": self.websocket_type,
            "isClose": self.is_close,
        }


@dataclass
class HTTPRequest:
    method: str = ""
    url: str = ""
    client_ip: str = ""
    time: str = ""
    process_name: str = ""
    proto: str = ""
    header: Header = field(default_factory=dict)
    body: bytes = b""
    body_length: int = 0
    is_max_length: bool = False


@dataclass
class HTTPResponse:
    time: str = ""
    code: str = ""
    state: str = ""
    type: str = ""
    length: int = 0
    proto: str = ""
    header: Header = field(default_factory=dict)
    body: bytes = b""
    response_type: str = ""
    server_ip: str = ""
    body_length: int = 0
    is_max_length: bool = False


@dataclass
class HTTPSession:
    request: HTTPRequest = field(default_factory=HTTPRequest)
    response: HTTPResponse = field(default_factory=HTTPResponse)
    state: int = 0
    is_websocket: bool = False
    websocket_disconnect: bool = False
    streams: List[Frame] = field(default_factory=list)
    stream_keys: List[int] = field(default_factory=list)


@dataclass
class TCPSession:
    method: str = ""
    remote_address: str = ""
    host: str = ""
    time: str = ""
    streams: List[Frame] = field(default_factory=list)
    stream_keys: List[int] = field(default_factory=list)


@dataclass
class UDPSession:
    method: str = ""
    remote_address: str = ""
    time: str = ""
    streams: List[Frame] = field(default_factory=list)
    stream_keys: List[int] = field(default_factory=list)


@dataclass
class Record:
    """A single captured session.

    ``index`` is the 1-based position inside the file (the ``#`` column), not
    the SunnyNet GUI sequence number (that one lives in ``theology``).
    """

    index: int = 0
    kind: str = ""
    theology: int = 0

    method: str = ""
    url: str = ""
    host: str = ""
    path: str = ""
    query: str = ""
    status: str = ""
    process: str = ""
    client_ip: str = ""
    server_ip: str = ""
    remote: str = ""
    time: str = ""
    note: str = ""
    user_name: str = ""
    ico: str = ""
    error: str = ""

    rec_length: int = 0
    sen_length: int = 0

    http: Optional[HTTPSession] = None
    tcp: Optional[TCPSession] = None
    udp: Optional[UDPSession] = None

    # -- derived helpers -------------------------------------------------

    @property
    def frames(self) -> List[Frame]:
        session = self.http or self.tcp or self.udp
        return list(session.streams) if session is not None else []

    @property
    def req_body(self) -> bytes:
        return self.http.request.body if self.http is not None else b""

    @property
    def resp_body(self) -> bytes:
        return self.http.response.body if self.http is not None else b""

    @property
    def req_header(self) -> Header:
        return self.http.request.header if self.http is not None else {}

    @property
    def resp_header(self) -> Header:
        return self.http.response.header if self.http is not None else {}

    @property
    def body_size(self) -> int:
        return len(self.req_body) + len(self.resp_body) + sum(
            len(f.body) for f in self.frames
        )

    @property
    def display_url(self) -> str:
        return self.url or self.host or self.remote

    def header_value(self, name: str, response: bool = False) -> str:
        """First header value matching ``name`` (case-insensitive)."""

        header = self.resp_header if response else self.req_header
        lowered = name.lower()
        for key, values in header.items():
            if key.lower() == lowered and values:
                return values[0]
        return ""

    def to_summary(self) -> dict:
        return {
            "index": self.index,
            "kind": self.kind,
            "theology": self.theology,
            "method": self.method,
            "status": self.status,
            "host": self.host,
            "url": self.url,
            "process": self.process,
            "clientIP": self.client_ip,
            "time": self.time,
            "note": self.note,
            "error": self.error,
            "recLength": self.rec_length,
            "senLength": self.sen_length,
            "bodyBytes": self.body_size,
            "frames": len(self.frames),
        }

    def to_dict(self) -> dict:
        data = self.to_summary()
        data.update(
            {
                "path": self.path,
                "query": self.query,
                "serverIP": self.server_ip or self.remote,
                "userName": self.user_name,
            }
        )
        if self.http is not None:
            data["isWebsocket"] = self.http.is_websocket
            data["request"] = {
                "method": self.http.request.method,
                "url": self.http.request.url,
                "clientIP": self.http.request.client_ip,
                "time": self.http.request.time,
                "processName": self.http.request.process_name,
                "proto": self.http.request.proto,
                "header": self.http.request.header,
                "bodyLength": self.http.request.body_length,
                "isMaxLength": self.http.request.is_max_length,
            }
            data["response"] = {
                "time": self.http.response.time,
                "code": self.http.response.code,
                "state": self.http.response.state,
                "type": self.http.response.type,
                "length": self.http.response.length,
                "proto": self.http.response.proto,
                "header": self.http.response.header,
                "responseType": self.http.response.response_type,
                "serverIP": self.http.response.server_ip,
                "bodyLength": self.http.response.body_length,
                "isMaxLength": self.http.response.is_max_length,
            }
        if self.tcp is not None:
            data["tcp"] = {
                "method": self.tcp.method,
                "remoteAddress": self.tcp.remote_address,
                "host": self.tcp.host,
                "time": self.tcp.time,
            }
        if self.udp is not None:
            data["udp"] = {
                "method": self.udp.method,
                "remoteAddress": self.udp.remote_address,
                "time": self.udp.time,
            }
        frames = self.frames
        if frames:
            data["streams"] = [f.to_dict() for f in frames]
        return data


def fill_derived(record: Record) -> None:
    """Populate the flat fields (kind/host/path/status/...) from the session."""

    if record.http is not None:
        session = record.http
        request = session.request
        record.method = request.method
        record.url = request.url
        record.process = request.process_name
        record.client_ip = request.client_ip
        record.time = request.time
        record.server_ip = session.response.server_ip
        record.status = session.response.code
        if session.is_websocket:
            record.kind = KIND_WEBSOCKET
            if not record.method:
                record.method = "WS"
        else:
            record.kind = KIND_HTTP
        if request.url:
            try:
                parts = urlsplit(request.url)
            except ValueError:
                parts = None
            if parts is not None:
                record.host = parts.netloc.rsplit("@", 1)[-1]
                record.path = parts.path
                record.query = parts.query
    elif record.tcp is not None:
        session = record.tcp
        record.kind = KIND_TCP
        record.method = session.method
        record.host = session.host
        record.remote = session.remote_address
        record.url = session.host or session.remote_address
        record.time = session.time
    elif record.udp is not None:
        session = record.udp
        record.kind = KIND_UDP
        record.method = session.method
        record.remote = session.remote_address
        record.host = session.remote_address
        record.url = session.remote_address
        record.time = session.time


@dataclass
class Archive:
    """A decoded ``.sy4`` file."""

    path: str = ""
    compressed: bool = False
    header_count: int = 0
    records: List[Record] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def by_index(self, index: int) -> Optional[Record]:
        for record in self.records:
            if record.index == index:
                return record
        return None

    def by_theology(self, theology: int) -> Optional[Record]:
        for record in self.records:
            if record.theology == theology:
                return record
        return None
