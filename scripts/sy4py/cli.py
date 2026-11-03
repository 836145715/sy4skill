"""Command line interface for sy4py."""

from __future__ import annotations

import json
import sys
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import __version__
from .content import content_encoding, decompress_body, hexdump
from .decoder import open_file
from .encoder import write_file
from .errors import Sy4Error, UsageError
from .model import Record
from .query import Query
from .redact import redact_record
from .render import (
    cut,
    dump_json,
    format_table,
    frame_direction,
    header_lines,
    human_bytes,
    print_body,
    record_json,
    summaries,
)
from .search import SearchOptions, search
from .stats import group_by, summarize

USAGE = """sy4py — inspect SunnyNetV4 (.sy4) capture files

Usage:
  sy4py info     <file> [filter]
  sy4py list     <file> [filter] [--wide]
  sy4py get      <file> <index> [--full] [--redact] [--json]
  sy4py search   <file> <needle> [filter] [--in ...] [--encoding ...]
  sy4py stats    <file> [filter] [--by host|method|status|process|type|client|server|user]
  sy4py streams  <file> <index> [--json]
  sy4py body     <file> <index> [--part req|resp] [--stream N] [--out file]
                 [--hex] [--decompress]
  sy4py export   <file> <out.sy4|out.jsonl> [filter] [--jsonl] [--raw] [--full]

Filters (info / list / search / stats / export):
  --type http|ws|tcp,udp       comma separated OR
  --method GET,POST            --host apple.com,alipay.com
  --url substring              --path /v1
  --status 200,302,401         --process chrome
  --client 127.0.0.1           --server 10.0.0.
  --note text                  --user account
  --error                      only records with a non-empty error
  --no-status                  only records without a status code
  --noise                      drop 304 / CDN / images / fonts / telemetry
  --min-body N                 total body bytes
  --theology N                 --index N
  --e "type=http status=401 or status=403"
  --limit N                    --offset N
  --json

Expression syntax:
  fields: type method host url path status process client server note user
          error index theology rec sen frames
  operators: = != ~ !~ > < >= <=
  whitespace is AND, `or` / `||` is OR, commas OR values (status=401,403)

Search options:
  --in url,header,req,resp,stream,note,error,all
  --encoding auto|utf8|hex|base64
  --ignore-case / --case-sensitive    --strip-space

Examples:
  sy4py info capture.sy4
  sy4py list capture.sy4 --noise --method POST --host api.example.com
  sy4py search capture.sy4 checkout --in url --noise --limit 20
  sy4py get capture.sy4 509 --redact
  sy4py body capture.sy4 509 --part resp --decompress --out resp.json
"""

BOOL_FLAGS = {
    "json",
    "noise",
    "no-status",
    "error",
    "wide",
    "full",
    "redact",
    "ignore-case",
    "case-sensitive",
    "strip-space",
    "jsonl",
    "raw",
    "hex",
    "decompress",
    "help",
}

VALUE_FLAGS = {
    "type",
    "method",
    "host",
    "url",
    "path",
    "status",
    "process",
    "client",
    "server",
    "note",
    "user",
    "min-body",
    "theology",
    "index",
    "e",
    "limit",
    "offset",
    "in",
    "encoding",
    "by",
    "part",
    "stream",
    "out",
}

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point; returns a process exit code."""

    _configure_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0 if args else 2
    if args[0] in ("-V", "--version", "version"):
        print("sy4py %s" % __version__)
        return 0

    command, rest = args[0], args[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print("error: unknown command %r" % command, file=sys.stderr)
        print("run `sy4py --help` for usage", file=sys.stderr)
        return 2
    try:
        return handler(rest)
    except Sy4Error as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print("error: file not found: %s" % exc, file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 1


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


# ---------------------------------------------------------------------------
# flag parsing (Go `flag` compatible: flags may follow positionals)
# ---------------------------------------------------------------------------


def parse_flags(args: Sequence[str]) -> Tuple[Dict[str, object], List[str]]:
    flags: Dict[str, object] = {}
    positional: List[str] = []
    index = 0
    total = len(args)
    while index < total:
        arg = args[index]
        if arg == "--":
            positional.extend(args[index + 1 :])
            break
        if not arg.startswith("-") or arg == "-":
            positional.append(arg)
            index += 1
            continue
        name = arg.lstrip("-")
        value: Optional[str] = None
        if "=" in name:
            name, value = name.split("=", 1)
        if name in BOOL_FLAGS:
            flags[name] = _bool_value(name, value)
            index += 1
            continue
        if name not in VALUE_FLAGS:
            raise UsageError("unknown flag --%s" % name)
        if value is None:
            if index + 1 >= total or args[index + 1].startswith("-"):
                raise UsageError("flag --%s needs a value" % name)
            value = args[index + 1]
            index += 1
        flags[name] = value
        index += 1
    return flags, positional


def _bool_value(name: str, value: Optional[str]) -> bool:
    if value is None:
        return True
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise UsageError("flag --%s expects true/false, got %r" % (name, value))


def _int_flag(flags: Dict[str, object], name: str, default: int = 0) -> int:
    raw = flags.get(name)
    if raw is None:
        return default
    try:
        return int(str(raw), 10)
    except ValueError:
        raise UsageError("--%s expects a number, got %r" % (name, raw)) from None


def _text_flag(flags: Dict[str, object], name: str, default: str = "") -> str:
    raw = flags.get(name)
    return default if raw is None else str(raw)


def query_from_flags(flags: Dict[str, object]) -> Query:
    query = Query()
    query.type = _text_flag(flags, "type")
    query.method = _text_flag(flags, "method")
    query.host = _text_flag(flags, "host")
    query.url = _text_flag(flags, "url")
    query.path = _text_flag(flags, "path")
    query.status = _text_flag(flags, "status")
    query.process = _text_flag(flags, "process")
    query.client = _text_flag(flags, "client")
    query.server = _text_flag(flags, "server")
    query.note = _text_flag(flags, "note")
    query.user = _text_flag(flags, "user")
    query.has_error = bool(flags.get("error"))
    query.no_status = bool(flags.get("no-status"))
    query.skip_noise = bool(flags.get("noise"))
    query.index = _int_flag(flags, "index")
    query.theology = _int_flag(flags, "theology")
    query.min_body = _int_flag(flags, "min-body")
    query.expr = _text_flag(flags, "e")
    query.limit = _int_flag(flags, "limit")
    query.offset = _int_flag(flags, "offset")
    return query


def _require_file(positional: Sequence[str], usage: str) -> str:
    if not positional:
        raise UsageError(usage)
    return positional[0]


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_info(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    path = _require_file(positional, "usage: sy4py info <file>")
    archive = open_file(path)
    query = query_from_flags(flags)
    matched = query.apply(archive.records)
    stats = summarize(matched)

    if flags.get("json"):
        dump_json(
            {
                "path": archive.path,
                "compressed": archive.compressed,
                "headerCount": archive.header_count,
                "parsed": len(archive),
                "matched": len(matched),
                "stats": stats.to_dict(),
            }
        )
        return 0

    print("File: %s" % archive.path)
    print("Compressed: %s" % ("yes" if archive.compressed else "no"))
    print("Header count: %d" % archive.header_count)
    print("Parsed: %d" % len(archive))
    if len(matched) != len(archive):
        print("Matched: %d" % len(matched))
    print(
        "http=%d  websocket=%d  tcp=%d  udp=%d  errors=%d  frames=%d  body=%s"
        % (
            stats.http,
            stats.websocket,
            stats.tcp,
            stats.udp,
            stats.errors,
            stats.frames,
            human_bytes(stats.body_bytes),
        )
    )
    return 0


def cmd_list(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    path = _require_file(positional, "usage: sy4py list <file>")
    archive = open_file(path)
    matched = query_from_flags(flags).apply(archive.records)

    if flags.get("json"):
        dump_json({"count": len(matched), "records": summaries(matched)})
        return 0

    url_width = 0 if flags.get("wide") else 80
    rows = []
    for record in matched:
        url = record.display_url
        if url_width:
            url = cut(url, url_width)
        rows.append(
            [
                str(record.index),
                cut(record.time, 12),
                record.kind,
                cut(record.method, 8),
                cut(record.status, 6),
                human_bytes(record.body_size),
                cut(record.process, 16),
                url,
            ]
        )
    print("Total %d records" % len(matched))
    print(
        format_table(
            ["#", "TIME", "KIND", "METHOD", "STATUS", "BODY", "PROCESS", "URL"],
            rows,
        )
    )
    return 0


def cmd_get(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    if len(positional) < 2:
        raise UsageError("usage: sy4py get <file> <index>")
    path = positional[0]
    try:
        index = int(positional[1], 10)
    except ValueError:
        raise UsageError("index must be a number, got %r" % positional[1]) from None

    archive = open_file(path)
    record = archive.by_index(index)
    theology = _int_flag(flags, "theology")
    if record is None and theology > 0:
        record = archive.by_theology(theology)
    if record is None:
        raise Sy4Error("record #%d not found" % index)
    if flags.get("redact"):
        record = redact_record(record)

    full = bool(flags.get("full"))
    if flags.get("json"):
        dump_json(record_json(record, full))
        return 0
    _print_record(record, full)
    return 0


def _print_record(record: Record, full: bool) -> None:
    print("#%d  %s  theology=%d" % (record.index, record.kind, record.theology))
    print("Method: %s" % record.method)
    print("URL: %s" % record.display_url)
    if record.status:
        print("Status: %s" % record.status)
    print("Process: %s" % record.process)
    print("Client: %s" % record.client_ip)
    if record.server_ip or record.remote:
        print("Server: %s" % (record.server_ip or record.remote))
    print("Time: %s" % record.time)
    if record.note:
        print("Note: %s" % record.note)
    if record.error:
        print("Error: %s" % record.error)
    print("Recv/Send: %d / %d" % (record.rec_length, record.sen_length))

    if record.http is not None:
        print("\n[Request headers]")
        print(header_lines(record.http.request.header) or "(empty)")
        print("\n[Request body] %d bytes" % len(record.http.request.body))
        print_body(record.http.request.body, full)
        print("\n[Response headers]")
        print(header_lines(record.http.response.header) or "(empty)")
        print("\n[Response body] %d bytes" % len(record.http.response.body))
        print_body(record.http.response.body, full)
        if record.http.streams:
            print(
                "\n[WebSocket] %d frames, use `sy4py streams %s %d`"
                % (len(record.http.streams), record.index, record.index)
            )
    elif record.frames:
        print("\n[Stream] %d frames, use `sy4py streams` to inspect" % len(record.frames))


def cmd_search(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    if len(positional) < 2:
        raise UsageError("usage: sy4py search <file> <needle>")
    path = positional[0]
    needle = " ".join(positional[1:])

    archive = open_file(path)
    matched = query_from_flags(flags).apply(archive.records)
    options = SearchOptions(
        scope=_text_flag(flags, "in", "all"),
        case_insensitive=not bool(flags.get("case-sensitive")),
        strip_space=bool(flags.get("strip-space")),
        encoding=_text_flag(flags, "encoding", "auto"),
    )
    if flags.get("ignore-case") is False:
        options.case_insensitive = False
    hits = search(matched, needle, options)

    if flags.get("json"):
        dump_json(
            {
                "needle": needle,
                "count": len(hits),
                "hits": [hit.to_dict() for hit in hits],
            }
        )
        return 0

    print("Hits: %d" % len(hits))
    rows = [
        ["#%d" % hit.index, hit.field, hit.snippet.replace("\n", " ")] for hit in hits
    ]
    if rows:
        print(format_table(["#", "FIELD", "SNIPPET"], rows))
    return 0


def cmd_stats(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    path = _require_file(positional, "usage: sy4py stats <file>")
    archive = open_file(path)
    matched = query_from_flags(flags).apply(archive.records)

    by = _text_flag(flags, "by")
    if by:
        rows = group_by(matched, by)
        if flags.get("json"):
            dump_json(
                {
                    "by": by,
                    "total": len(matched),
                    "rows": [row.to_dict() for row in rows],
                }
            )
            return 0
        print("Grouped by %s, %d records" % (by, len(matched)))
        for row in rows:
            print("%6d  %s" % (row.count, row.key))
        return 0

    stats = summarize(matched)
    if flags.get("json"):
        dump_json(stats.to_dict())
        return 0
    print(
        "Total %d  http=%d ws=%d tcp=%d udp=%d errors=%d"
        % (
            stats.total,
            stats.http,
            stats.websocket,
            stats.tcp,
            stats.udp,
            stats.errors,
        )
    )
    _print_counters("Type", stats.by_type)
    _print_counters("Method", stats.by_method)
    _print_counters("Status", stats.by_status)
    _print_counters("Host", stats.by_host)
    _print_counters("Process", stats.by_process)
    return 0


def _print_counters(title: str, rows) -> None:
    if not rows:
        return
    print("\n[%s]" % title)
    for row in rows:
        print("%6d  %s" % (row.count, row.key))


def cmd_streams(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    if len(positional) < 2:
        raise UsageError("usage: sy4py streams <file> <index>")
    try:
        index = int(positional[1], 10)
    except ValueError:
        raise UsageError("index must be a number, got %r" % positional[1]) from None

    archive = open_file(positional[0])
    record = archive.by_index(index)
    if record is None:
        raise Sy4Error("record #%d not found" % index)
    frames = record.frames

    if flags.get("json"):
        dump_json(
            {
                "index": record.index,
                "count": len(frames),
                "streams": [
                    {
                        "i": position,
                        "key": frame.key,
                        "messageId": frame.message_id,
                        "dir": frame_direction(frame),
                        "length": len(frame.body),
                        "time": frame.time,
                        "close": frame.is_close,
                        "preview": _preview(frame.body, 60),
                    }
                    for position, frame in enumerate(frames)
                ],
            }
        )
        return 0

    print("#%d %s  %d frames" % (record.index, record.kind, len(frames)))
    rows = [
        [
            str(position),
            frame_direction(frame),
            str(len(frame.body)),
            "yes" if frame.is_close else "",
            cut(frame.time, 8),
            _preview(frame.body, 50),
        ]
        for position, frame in enumerate(frames)
    ]
    if rows:
        print(format_table(["i", "DIR", "LEN", "CLOSE", "TIME", "PREVIEW"], rows))
    return 0


def _preview(body: bytes, limit: int) -> str:
    from .render import preview_bytes

    return preview_bytes(body, limit)


def cmd_body(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    if len(positional) < 2:
        raise UsageError("usage: sy4py body <file> <index>")
    try:
        index = int(positional[1], 10)
    except ValueError:
        raise UsageError("index must be a number, got %r" % positional[1]) from None

    archive = open_file(positional[0])
    record = archive.by_index(index)
    if record is None:
        raise Sy4Error("record #%d not found" % index)

    part = _text_flag(flags, "part", "resp").lower()
    stream = _int_flag(flags, "stream", -1)
    header: dict = {}
    if stream >= 0:
        frames = record.frames
        if stream >= len(frames):
            raise Sy4Error(
                "stream index out of range: %d frames available" % len(frames)
            )
        body = frames[stream].body
    elif part in ("req", "request"):
        body = record.req_body
        header = record.req_header
    elif part in ("resp", "response"):
        body = record.resp_body
        header = record.resp_header
    else:
        raise UsageError("--part must be req or resp, got %r" % part)

    if flags.get("decompress"):
        decoded = decompress_body(body, content_encoding(header))
        if decoded is not None:
            body = decoded
        else:
            print("warning: body is not gzip/deflate/br encoded", file=sys.stderr)

    out_path = _text_flag(flags, "out")
    if out_path:
        with open(out_path, "wb") as handle:
            handle.write(body)
        print("wrote %d bytes to %s" % (len(body), out_path))
        return 0

    if flags.get("hex"):
        sys.stdout.write(hexdump(body))
        return 0

    from .content import decode_text_or_none

    text = decode_text_or_none(body)
    if text is not None:
        sys.stdout.write(text)
        if body and not body.endswith(b"\n"):
            sys.stdout.write("\n")
    else:
        sys.stdout.write(hexdump(body))
    return 0


def cmd_export(args: Sequence[str]) -> int:
    flags, positional = parse_flags(args)
    if len(positional) < 2:
        raise UsageError("usage: sy4py export <file> <out.sy4|out.jsonl>")
    archive = open_file(positional[0])
    matched = query_from_flags(flags).apply(archive.records)
    out_path = positional[1]
    full = bool(flags.get("full"))

    if flags.get("jsonl") or out_path.lower().endswith(".jsonl"):
        with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
            for record in matched:
                payload = record_json(record, full) if full else record.to_summary()
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        print("exported %d records to %s" % (len(matched), out_path))
        return 0

    compress = not bool(flags.get("raw"))
    write_file(out_path, matched, compress=compress)
    print("exported %d records to %s" % (len(matched), out_path))
    return 0


COMMANDS: Dict[str, Callable[[Sequence[str]], int]] = {
    "info": cmd_info,
    "list": cmd_list,
    "get": cmd_get,
    "search": cmd_search,
    "stats": cmd_stats,
    "streams": cmd_streams,
    "body": cmd_body,
    "export": cmd_export,
}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
