"""Aggregations used by ``sy4py stats``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .model import (
    KIND_HTTP,
    KIND_TCP,
    KIND_UDP,
    KIND_WEBSOCKET,
    Record,
)


@dataclass
class Counter:
    key: str
    count: int

    def to_dict(self) -> dict:
        return {"key": self.key, "count": self.count}


@dataclass
class Stats:
    total: int = 0
    http: int = 0
    websocket: int = 0
    tcp: int = 0
    udp: int = 0
    errors: int = 0
    frames: int = 0
    body_bytes: int = 0
    by_type: List[Counter] = field(default_factory=list)
    by_method: List[Counter] = field(default_factory=list)
    by_status: List[Counter] = field(default_factory=list)
    by_host: List[Counter] = field(default_factory=list)
    by_process: List[Counter] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "http": self.http,
            "websocket": self.websocket,
            "tcp": self.tcp,
            "udp": self.udp,
            "errors": self.errors,
            "frames": self.frames,
            "bodyBytes": self.body_bytes,
            "byType": [row.to_dict() for row in self.by_type],
            "byMethod": [row.to_dict() for row in self.by_method],
            "byStatus": [row.to_dict() for row in self.by_status],
            "byHost": [row.to_dict() for row in self.by_host],
            "byProcess": [row.to_dict() for row in self.by_process],
        }


def summarize(records: Iterable[Record]) -> Stats:
    records = list(records)
    stats = Stats(total=len(records))
    types: Dict[str, int] = {}
    methods: Dict[str, int] = {}
    statuses: Dict[str, int] = {}
    hosts: Dict[str, int] = {}
    processes: Dict[str, int] = {}

    for record in records:
        types[record.kind] = types.get(record.kind, 0) + 1
        if record.kind == KIND_HTTP:
            stats.http += 1
        elif record.kind == KIND_WEBSOCKET:
            stats.websocket += 1
        elif record.kind == KIND_TCP:
            stats.tcp += 1
        elif record.kind == KIND_UDP:
            stats.udp += 1
        if record.error:
            stats.errors += 1
        stats.frames += len(record.frames)
        stats.body_bytes += record.body_size
        if record.method:
            methods[record.method] = methods.get(record.method, 0) + 1
        if record.status:
            statuses[record.status] = statuses.get(record.status, 0) + 1
        if record.host:
            hosts[record.host] = hosts.get(record.host, 0) + 1
        if record.process:
            processes[record.process] = processes.get(record.process, 0) + 1

    stats.by_type = ranked(types)
    stats.by_method = ranked(methods)
    stats.by_status = ranked(statuses)
    stats.by_host = ranked(hosts, limit=30)
    stats.by_process = ranked(processes, limit=30)
    return stats


def group_by(records: Iterable[Record], field: str) -> List[Counter]:
    buckets: Dict[str, int] = {}
    for record in records:
        key = _group_key(record, field) or "(empty)"
        buckets[key] = buckets.get(key, 0) + 1
    return ranked(buckets)


def _group_key(record: Record, field: str) -> str:
    field = (field or "").lower()
    if field in ("type", "kind"):
        return record.kind
    if field == "method":
        return record.method
    if field in ("status", "code"):
        return record.status
    if field == "host":
        return record.host
    if field == "process":
        return record.process
    if field == "client":
        return record.client_ip
    if field == "server":
        return record.server_ip or record.remote
    if field == "user":
        return record.user_name
    return record.kind


def ranked(buckets: Dict[str, int], limit: int = 0) -> List[Counter]:
    rows = [Counter(key, count) for key, count in buckets.items()]
    rows.sort(key=lambda row: (-row.count, row.key))
    if limit > 0:
        rows = rows[:limit]
    return rows
