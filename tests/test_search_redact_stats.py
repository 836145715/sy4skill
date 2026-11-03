"""Search, redaction and stats tests."""

from __future__ import annotations

import base64

import pytest

from sy4py.model import fill_derived
from sy4py.redact import redact_header, redact_record, redact_url
from sy4py.search import SearchOptions, search
from sy4py.stats import group_by, summarize


@pytest.fixture()
def loaded(records):
    for record in records:
        fill_derived(record)
    return records


def test_search_url(loaded):
    hits = search(loaded, "example.com", SearchOptions(scope="url"))
    assert hits and all(hit.field == "url" for hit in hits)


def test_search_body(loaded):
    hits = search(loaded, "alice", SearchOptions(scope="resp,req"))
    fields = {hit.field for hit in hits}
    assert "request.body" in fields


def test_search_note(loaded):
    hits = search(loaded, "login flow", SearchOptions(scope="note"))
    assert len(hits) == 1
    assert hits[0].index == 1


def test_search_stream_frames(loaded):
    hits = search(loaded, '{"ping":1}', SearchOptions(scope="stream"))
    assert len(hits) == 1
    assert hits[0].field == "stream[1].body"


def test_search_case_insensitive_default(loaded):
    assert search(loaded, "ALICE", SearchOptions(scope="req"))


def test_search_case_sensitive(loaded):
    assert search(loaded, "ALICE", SearchOptions(scope="resp", case_insensitive=False)) == []


def test_search_hex_needle(loaded):
    needle = b"alice".hex()
    hits = search(loaded, needle, SearchOptions(scope="req", encoding="hex"))
    assert hits


def test_search_base64_needle(loaded):
    needle = base64.b64encode(b"alice").decode()
    hits = search(loaded, needle, SearchOptions(scope="req", encoding="base64"))
    assert hits


def test_search_empty_needle(loaded):
    from sy4py.errors import QueryError

    with pytest.raises(QueryError):
        search(loaded, "  ", SearchOptions(strip_space=True))


def test_redact_header():
    header = {
        "Cookie": ["sid=1"],
        "Authorization": ["Bearer x"],
        "X-Api-Token": ["abc"],
        "Accept": ["*/*"],
    }
    redacted = redact_header(header)
    assert redacted["Cookie"] == ["***"]
    assert redacted["Authorization"] == ["***"]
    assert redacted["X-Api-Token"] == ["***"]
    assert redacted["Accept"] == ["*/*"]
    assert header["Cookie"] == ["sid=1"]


def test_redact_url():
    url = "https://a.example.com/cb?token=abc&page=2&sessionId=xyz#frag"
    redacted = redact_url(url)
    assert "token=***" in redacted
    assert "sessionId" in redacted
    assert "page=2" in redacted
    assert redacted.endswith("#frag")


def test_redact_record_keeps_original(loaded):
    record = loaded[0]
    clone = redact_record(record)
    assert clone.http.request.header["Cookie"] == ["***"]
    assert "token=***" in clone.url
    assert record.http.request.header["Cookie"] == ["sid=abcdef"]
    assert "token=secret" in record.url


def test_summarize(loaded):
    stats = summarize(loaded)
    assert stats.total == 4
    assert stats.http == 1
    assert stats.websocket == 1
    assert stats.tcp == 1
    assert stats.udp == 1
    assert stats.frames == 4


def test_group_by_host(loaded):
    rows = group_by(loaded, "host")
    assert sum(row.count for row in rows) == 4
    counts = {row.key: row.count for row in rows}
    assert counts["api.example.com"] == 1
    assert counts["8.8.8.8:53"] == 1


def test_group_by_unknown_field_falls_back_to_kind(loaded):
    rows = group_by(loaded, "nonsense")
    assert {row.key for row in rows} == {"http", "websocket", "tcp", "udp"}
