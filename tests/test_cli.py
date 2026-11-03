"""End-to-end CLI tests (no subprocess needed: ``main`` returns an exit code)."""

from __future__ import annotations

import json

import pytest

from sy4py.cli import main
from sy4py.decoder import open_file
from sy4py.encoder import write_file


def _write(tmp_path, records, compress=True, name="sample.sy4") -> str:
    path = tmp_path / name
    write_file(str(path), records, compress=compress)
    return str(path)


def test_info_json(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["info", path, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parsed"] == 4
    assert payload["headerCount"] == 4
    assert payload["compressed"] is True
    assert payload["stats"]["total"] == 4


def test_info_text(tmp_path, records, capsys):
    path = _write(tmp_path, records, compress=False)
    assert main(["info", path]) == 0
    out = capsys.readouterr().out
    assert "Header count: 4" in out
    assert "http=1" in out


def test_list_json_and_table(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["list", path, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 4
    assert payload["records"][0]["method"] == "POST"

    assert main(["list", path, "--wide"]) == 0
    out = capsys.readouterr().out
    assert "https://api.example.com/v1/login" in out


def test_list_filters(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["list", path, "--json", "--type", "ws"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert main(["list", path, "--json", "--e", "status=200 or status=101"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2


def test_get_json(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["get", path, "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["request"]["body"] == '{"user":"alice"}'
    assert payload["response"]["body"] == '{"ok":true}'
    assert payload["response"]["code"] == "200"


def test_get_redact(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["get", path, "1", "--json", "--redact"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["request"]["header"]["Cookie"] == ["***"]
    assert "token=***" in payload["url"]


def test_get_missing_index(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["get", path, "99"]) == 1
    assert "not found" in capsys.readouterr().err


def test_get_text_output(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["get", path, "2"]) == 0
    out = capsys.readouterr().out
    assert "[Request headers]" in out
    assert "[WebSocket]" in out


def test_body_to_file(tmp_path, records):
    path = _write(tmp_path, records)
    out = tmp_path / "body.bin"
    assert main(["body", path, "1", "--part", "req", "--out", str(out)]) == 0
    assert out.read_bytes() == b'{"user":"alice"}'


def test_body_stdout(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["body", path, "1", "--part", "resp"]) == 0
    assert capsys.readouterr().out.strip() == '{"ok":true}'


def test_body_decompress(tmp_path, gzip_http_record):
    path = _write(tmp_path, [gzip_http_record])
    out = tmp_path / "decoded.json"
    assert main(["body", path, "1", "--decompress", "--out", str(out)]) == 0
    assert out.read_bytes() == b'{"compressed":true,"items":[1,2,3]}'


def test_body_hex(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["body", path, "1", "--part", "req", "--hex"]) == 0
    assert "00000000" in capsys.readouterr().out


def test_body_stream_frame(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["body", path, "2", "--stream", "1"]) == 0
    assert capsys.readouterr().out.strip() == '{"ping":1}'


def test_body_bad_part(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["body", path, "1", "--part", "nope"]) == 1
    assert "--part" in capsys.readouterr().err


def test_streams_json(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["streams", path, "2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 2
    assert payload["streams"][1]["dir"] == "send"


def test_search_json(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["search", path, "alice", "--json", "--in", "req"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["hits"][0]["field"] == "request.body"


def test_stats_by_host(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["stats", path, "--by", "host", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    rows = {row["key"]: row["count"] for row in payload["rows"]}
    assert rows["api.example.com"] == 1
    assert sum(rows.values()) == 4


def test_stats_text(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["stats", path]) == 0
    out = capsys.readouterr().out
    assert "Total 4" in out
    assert "[Host]" in out


def test_export_raw(tmp_path, records):
    path = _write(tmp_path, records)
    out = tmp_path / "out.sy4"
    assert main(["export", path, str(out), "--raw"]) == 0
    archive = open_file(str(out))
    assert len(archive) == 4
    assert archive.compressed is False


def test_export_jsonl(tmp_path, records):
    path = _write(tmp_path, records)
    out = tmp_path / "out.jsonl"
    assert main(["export", path, str(out), "--limit", "2"]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["index"] == 1


def test_export_jsonl_full_contains_bodies(tmp_path, records):
    path = _write(tmp_path, records)
    out = tmp_path / "full.jsonl"
    assert main(["export", path, str(out), "--full", "--limit", "1"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert payload["response"]["body"] == '{"ok":true}'


def test_missing_file(tmp_path, capsys):
    assert main(["info", str(tmp_path / "nope.sy4")]) == 1
    assert "file not found" in capsys.readouterr().err


def test_unknown_flag(tmp_path, records, capsys):
    path = _write(tmp_path, records)
    assert main(["list", path, "--bogus"]) == 1
    assert "unknown flag" in capsys.readouterr().err


def test_unknown_command(capsys):
    assert main(["nope"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_help(capsys):
    assert main(["--help"]) == 0
    assert "sy4py info" in capsys.readouterr().out


def test_version(capsys):
    assert main(["--version"]) == 0
    assert "sy4py" in capsys.readouterr().out


def test_json_binary_body_is_hex(tmp_path, capsys):
    from conftest import make_http_record

    record = make_http_record(
        1,
        method="GET",
        request_body=b"",
        response_body=b"\x00\x01\x02\xff",
        response_header={"Content-Type": ["application/octet-stream"]},
    )
    path = _write(tmp_path, [record])
    assert main(["get", path, "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["response"]["body"] == {
        "encoding": "hex",
        "data": "000102ff",
    }


def test_gzip_body_preview_in_get(tmp_path, gzip_http_record, capsys):
    path = _write(tmp_path, [gzip_http_record])
    assert main(["get", path, "1"]) == 0
    out = capsys.readouterr().out
    assert "[Response body]" in out
