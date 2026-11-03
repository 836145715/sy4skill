"""Decoder/encoder round-trip and robustness tests."""

from __future__ import annotations

import pytest

from sy4py import _brotli
from sy4py.decoder import decode_bytes, looks_raw, open_file
from sy4py.encoder import encode_archive, encode_records, write_file
from sy4py.errors import DecodeError
from sy4py.model import KIND_HTTP, KIND_TCP, KIND_UDP, KIND_WEBSOCKET, fill_derived


def test_raw_roundtrip(records, archive_bytes):
    assert looks_raw(archive_bytes)
    archive = decode_bytes(archive_bytes)
    assert archive.compressed is False
    assert archive.header_count == len(records)
    assert len(archive) == len(records)
    assert [r.index for r in archive] == [1, 2, 3, 4]
    assert [r.kind for r in archive] == [
        KIND_HTTP,
        KIND_WEBSOCKET,
        KIND_TCP,
        KIND_UDP,
    ]


def test_roundtrip_preserves_every_field(records, archive_bytes):
    for original in records:
        fill_derived(original)
    decoded = decode_bytes(archive_bytes)
    for expected, actual in zip(records, decoded):
        assert expected.to_dict() == actual.to_dict()
        assert expected.req_body == actual.req_body
        assert expected.resp_body == actual.resp_body
        assert [f.body for f in expected.frames] == [f.body for f in actual.frames]
        assert expected.rec_length == actual.rec_length


def test_compressed_roundtrip(records, compressed_bytes):
    if not _brotli.available():
        pytest.skip("brotli backend not installed")
    assert not looks_raw(compressed_bytes)
    archive = decode_bytes(compressed_bytes)
    assert archive.compressed is True
    assert len(archive) == len(records)


def test_write_and_open_file(tmp_path, records):
    path = tmp_path / "sample.sy4"
    write_file(str(path), records, compress=True)
    archive = open_file(str(path))
    assert archive.path == str(path)
    assert len(archive) == 4


def test_empty_file_rejected():
    with pytest.raises(DecodeError, match="empty"):
        decode_bytes(b"")


def test_truncated_stream_reports_record_number(archive_bytes):
    truncated = archive_bytes[: len(archive_bytes) - 10]
    with pytest.raises(DecodeError) as info:
        decode_bytes(truncated)
    assert "record" in str(info.value)


def test_unknown_record_type_rejected():
    payload = (1).to_bytes(8, "big") + b"9"
    with pytest.raises(DecodeError, match="unknown record type"):
        decode_bytes(payload)


def test_negative_length_rejected():
    payload = (1).to_bytes(8, "big") + b"1" + b"\xff" * 8
    with pytest.raises(DecodeError):
        decode_bytes(payload)


def test_encoder_requires_session():
    from sy4py.model import Record
    from sy4py.errors import Sy4Error

    with pytest.raises(Sy4Error):
        encode_records([Record(index=1)])


def test_derived_fields(records):
    record = records[0]
    fill_derived(record)
    assert record.host == "api.example.com"
    assert record.path == "/v1/login"
    assert record.query == "token=secret&page=2"
    assert record.status == "200"
    assert record.display_url.startswith("https://api.example.com")

    ws = records[1]
    fill_derived(ws)
    assert ws.kind == KIND_WEBSOCKET
    assert ws.method == "GET"
    assert len(ws.frames) == 2


def test_body_size_counts_frames(records):
    ws = records[1]
    fill_derived(ws)
    assert ws.body_size == len(b"hello") + len(b'{"ping":1}')


def test_looks_raw_zero_records():
    assert looks_raw((0).to_bytes(8, "big"))
    assert not looks_raw((0).to_bytes(8, "big") + b"\x00")


def test_export_after_decode_is_stable(tmp_path, records, archive_bytes):
    archive = decode_bytes(archive_bytes)
    path = tmp_path / "again.sy4"
    write_file(str(path), archive.records, compress=False)
    assert path.read_bytes() == encode_archive(archive.records, compress=False)
