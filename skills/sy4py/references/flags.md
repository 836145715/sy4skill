# sy4py CLI reference

## Commands

| Command | Purpose |
| --- | --- |
| `info <file>` | header count, parsed count, protocol/body stats |
| `list <file>` | record list, `--wide` for full URLs |
| `get <file> <index>` | one record: headers, bodies, stream summary |
| `search <file> <needle>` | full-text search with field + snippet |
| `stats <file>` | totals, or `--by <field>` grouping |
| `streams <file> <index>` | WebSocket / TCP / UDP frame list |
| `body <file> <index>` | extract request/response/frame body |
| `export <file> <out>` | write `.sy4` (compressed) or `.jsonl` |

## Filters

`info`, `list`, `search`, `stats`, `export` accept:

| Flag | Meaning |
| --- | --- |
| `--type http\|ws\|tcp,udp` | protocol, comma = OR |
| `--method GET,POST` | exact method, case-insensitive |
| `--host apple.com` | host substring |
| `--url /v1/order` | URL substring |
| `--path /v1` | path substring |
| `--status 200,302` | status codes |
| `--process chrome` | process name substring |
| `--client 127.0.0.1` | client address substring |
| `--server 10.0.0.` | server address substring |
| `--note keyword` | note substring |
| `--user account` | user name substring |
| `--error` | non-empty error only |
| `--no-status` | records without status code |
| `--noise` | drop 304 / CDN / static / telemetry |
| `--min-body N` | minimum total body bytes |
| `--theology N` | match SunnyNet GUI sequence number |
| `--index N` | match file index |
| `--e "<expr>"` | expression filter |
| `--limit N`, `--offset N` | pagination |
| `--json` | machine-readable output |

## Expression `--e`

Fields: `type method host url path status process client server note user error
index theology rec sen frames`.

Operators: `=` `!=` `~` `!~` `>` `<` `>=` `<=`.

Whitespace is AND, `or` / `||` is OR, commas OR values.

```bash
--e "type=http status>=400"
--e "status=401 or status=403"
--e "host~api process~chrome frames>0"
```

## Command specific flags

| Command | Flags |
| --- | --- |
| `list` | `--wide` |
| `get` | `--full`, `--redact` |
| `search` | `--in url,header,req,resp,stream,note,error,all`, `--encoding auto\|utf8\|hex\|base64`, `--ignore-case`, `--case-sensitive`, `--strip-space` |
| `stats` | `--by type\|method\|status\|host\|process\|client\|server\|user` |
| `body` | `--part req\|resp` (default `resp`), `--stream N`, `--out PATH`, `--hex`, `--decompress` |
| `export` | `--jsonl`, `--raw` (no Brotli), `--full` (JSONL with bodies) |

## JSON shapes

- `info`: `{path, compressed, headerCount, parsed, matched, stats}`
- `list`: `{count, records: [{index, kind, theology, method, status, host, url, process, clientIP, time, note, error, recLength, senLength, bodyBytes, frames}]}`
- `get`: record object plus `request` / `response` (`header`, `body`) and `streams`
- `search`: `{needle, count, hits: [{index, field, snippet}]}`
- `stats`: `{total, http, websocket, tcp, udp, errors, frames, bodyBytes, byType, byMethod, byStatus, byHost, byProcess}`
- `streams`: `{index, count, streams: [{i, key, messageId, dir, length, time, close, preview}]}`

Bodies in JSON are strings when printable, otherwise `{"encoding": "hex", "data": "..."}`.
`dir` is one of `recv`, `send`, `manual-send`, `close`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | runtime error (bad file, missing record, bad flag value) |
| 2 | unknown command / no arguments |
