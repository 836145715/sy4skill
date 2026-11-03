"""Record filtering and the ``--e`` expression language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from .errors import QueryError
from .model import Record
from .noise import is_noise

Predicate = Callable[[Record], bool]

_FIELDS = (
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
    "error",
    "index",
    "theology",
    "rec",
    "sen",
    "frames",
)

_OPERATORS = (">=", "<=", "!=", "!~", "=", "~", ">", "<")


@dataclass
class Query:
    """Declarative filter set; :meth:`apply` returns the matching records."""

    type: str = ""
    method: str = ""
    host: str = ""
    url: str = ""
    path: str = ""
    status: str = ""
    process: str = ""
    client: str = ""
    server: str = ""
    note: str = ""
    user: str = ""
    has_error: bool = False
    no_status: bool = False
    skip_noise: bool = False
    index: int = 0
    theology: int = 0
    min_rec: int = 0
    max_rec: int = 0
    min_sen: int = 0
    max_sen: int = 0
    min_body: int = 0
    expr: str = ""
    limit: int = 0
    offset: int = 0

    def predicates(self) -> List[Predicate]:
        preds: List[Predicate] = []
        if self.skip_noise:
            preds.append(lambda rec: not is_noise(rec))
        if self.no_status:
            preds.append(lambda rec: not rec.status)
        if self.type:
            preds.append(any_kind(self.type))
        if self.method:
            preds.append(
                any_exact_or_contains(lambda rec: rec.method, self.method, exact=True)
            )
        if self.host:
            preds.append(
                any_exact_or_contains(lambda rec: rec.host, self.host, exact=False)
            )
        if self.url:
            preds.append(contains_ci(lambda rec: rec.url, self.url))
        if self.path:
            preds.append(contains_ci(lambda rec: rec.path, self.path))
        if self.status:
            preds.append(
                any_exact_or_contains(lambda rec: rec.status, self.status, exact=True)
            )
        if self.process:
            preds.append(contains_ci(lambda rec: rec.process, self.process))
        if self.client:
            preds.append(contains_ci(lambda rec: rec.client_ip, self.client))
        if self.server:
            preds.append(
                contains_ci(
                    lambda rec: rec.server_ip or rec.remote, self.server
                )
            )
        if self.note:
            preds.append(contains_ci(lambda rec: rec.note, self.note))
        if self.user:
            preds.append(contains_ci(lambda rec: rec.user_name, self.user))
        if self.has_error:
            preds.append(lambda rec: bool(rec.error))
        if self.index > 0:
            preds.append(lambda rec: rec.index == self.index)
        if self.theology > 0:
            preds.append(lambda rec: rec.theology == self.theology)
        if self.min_rec > 0:
            preds.append(lambda rec: rec.rec_length >= self.min_rec)
        if self.max_rec > 0:
            preds.append(lambda rec: rec.rec_length <= self.max_rec)
        if self.min_sen > 0:
            preds.append(lambda rec: rec.sen_length >= self.min_sen)
        if self.max_sen > 0:
            preds.append(lambda rec: rec.sen_length <= self.max_sen)
        if self.min_body > 0:
            preds.append(lambda rec: rec.body_size >= self.min_body)
        if self.expr.strip():
            preds.append(parse_expr(self.expr))
        return preds

    def apply(self, records: Iterable[Record]) -> List[Record]:
        preds = self.predicates()
        matched = [
            record for record in records if all(pred(record) for pred in preds)
        ]
        if self.offset > 0:
            matched = matched[self.offset :]
        if self.limit > 0:
            matched = matched[: self.limit]
        return matched

    def is_empty(self) -> bool:
        """True when the query would keep every record (ignoring limit)."""

        return not self.predicates()


def contains_ci(get: Callable[[Record], str], needle: str) -> Predicate:
    lowered = needle.lower()
    return lambda rec: lowered in (get(rec) or "").lower()


def split_csv(spec: str) -> List[str]:
    return [item.strip() for item in spec.split(",") if item.strip()]


def any_kind(spec: str) -> Predicate:
    wanted = split_csv(spec)

    def check(rec: Record) -> bool:
        return any(kind_match(rec.kind, item) for item in wanted)

    return check


def any_exact_or_contains(
    get: Callable[[Record], str], spec: str, exact: bool
) -> Predicate:
    items = split_csv(spec)

    def check(rec: Record) -> bool:
        got = get(rec) or ""
        for item in items:
            if exact:
                if got.casefold() == item.casefold():
                    return True
            elif item.lower() in got.lower():
                return True
        return False

    return check


def kind_match(kind: str, wanted: str) -> bool:
    value = wanted.strip().lower()
    if value in ("http", "ws", "websocket", "tcp", "udp"):
        if value == "ws":
            value = "websocket"
        return kind == value
    return value in kind


def first_non_empty(first: str, second: str) -> str:
    return first or second


# ---------------------------------------------------------------------------
# --e expression language
# ---------------------------------------------------------------------------


def parse_expr(expr: str) -> Predicate:
    """Parse ``"host~api status=200 or status=401"`` into a predicate.

    Whitespace is AND, ``or`` / ``||`` is OR.  Values may be comma separated
    (``status=200,302``).
    """

    groups = split_or_groups(expr)
    if not groups:
        return lambda rec: True
    or_preds = [parse_and_group(group) for group in groups]

    def evaluate(rec: Record) -> bool:
        return any(pred(rec) for pred in or_preds)

    return evaluate


def parse_and_group(expr: str) -> Predicate:
    parts = split_expr(expr)
    if not parts:
        return lambda rec: True
    preds: List[Predicate] = []
    for part in parts:
        if part.lower() == "or" or part == "||":
            raise QueryError(
                "put `or` between conditions, e.g. status=401 or status=403"
            )
        preds.append(parse_clause(part))

    def evaluate(rec: Record) -> bool:
        return all(pred(rec) for pred in preds)

    return evaluate


def split_or_groups(expr: str) -> List[str]:
    out: List[str] = []
    current: List[str] = []
    quote = ""
    chars = list(expr)
    i = 0
    while i < len(chars):
        char = chars[i]
        if quote:
            if char == quote:
                quote = ""
            current.append(char)
            i += 1
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            i += 1
            continue
        if char == "|" and i + 1 < len(chars) and chars[i + 1] == "|":
            text = "".join(current).strip()
            if text:
                out.append(text)
            current = []
            i += 2
            continue
        if char in ("o", "O") and i + 1 < len(chars) and chars[i + 1] in ("r", "R"):
            prev_ok = i == 0 or chars[i - 1].isspace()
            next_index = i + 2
            next_ok = next_index == len(chars) or chars[next_index].isspace()
            if prev_ok and next_ok:
                text = "".join(current).strip()
                if text:
                    out.append(text)
                current = []
                i += 2
                continue
        current.append(char)
        i += 1
    text = "".join(current).strip()
    if text:
        out.append(text)
    return out


def split_expr(expr: str) -> List[str]:
    out: List[str] = []
    current: List[str] = []
    quote = ""
    for char in expr:
        if quote:
            if char == quote:
                quote = ""
            else:
                current.append(char)
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char.isspace():
            if current:
                out.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        out.append("".join(current))
    return out


def parse_clause(clause: str) -> Predicate:
    operator = ""
    position = -1
    for candidate in _OPERATORS:
        index = clause.find(candidate)
        if index > 0:
            operator = candidate
            position = index
            break
    if position <= 0:
        raise QueryError(
            "cannot parse %r, example: host~api status=200" % clause
        )
    field = clause[:position].strip().lower()
    value = clause[position + len(operator) :]
    return clause_predicate(field, operator, value)


def clause_predicate(field: str, operator: str, value: str) -> Predicate:
    if field in ("type", "kind"):
        return compare_string(lambda rec: rec.kind, operator, value, kind_field=True)
    if field == "method":
        return compare_string(lambda rec: rec.method, operator, value)
    if field == "host":
        return compare_string(lambda rec: rec.host, operator, value)
    if field == "url":
        return compare_string(lambda rec: rec.url, operator, value)
    if field == "path":
        return compare_string(lambda rec: rec.path, operator, value)
    if field in ("status", "code"):
        if operator in (">", "<", ">=", "<="):
            return compare_status(operator, value)
        return compare_string(lambda rec: rec.status, operator, value)
    if field == "process":
        return compare_string(lambda rec: rec.process, operator, value)
    if field == "client":
        return compare_string(lambda rec: rec.client_ip, operator, value)
    if field == "server":
        return compare_string(
            lambda rec: rec.server_ip or rec.remote, operator, value
        )
    if field == "note":
        return compare_string(lambda rec: rec.note, operator, value)
    if field == "user":
        return compare_string(lambda rec: rec.user_name, operator, value)
    if field == "error":
        return compare_string(lambda rec: rec.error, operator, value)
    if field == "index":
        return compare_int(lambda rec: rec.index, operator, value)
    if field == "theology":
        return compare_int(lambda rec: rec.theology, operator, value)
    if field == "rec":
        return compare_int(lambda rec: rec.rec_length, operator, value)
    if field == "sen":
        return compare_int(lambda rec: rec.sen_length, operator, value)
    if field == "frames":
        return compare_int(lambda rec: len(rec.frames), operator, value)
    raise QueryError(
        "unknown field %r (known: %s)" % (field, ", ".join(_FIELDS))
    )


def compare_string(
    get: Callable[[Record], str],
    operator: str,
    value: str,
    kind_field: bool = False,
) -> Predicate:
    items = split_csv(value) or [""]

    if operator in ("=", "=="):
        def equals(rec: Record) -> bool:
            got = get(rec) or ""
            for item in items:
                if kind_field:
                    if kind_match(got, item):
                        return True
                elif got.casefold() == item.casefold():
                    return True
            return False

        return equals

    if operator == "!=":
        def not_equals(rec: Record) -> bool:
            got = get(rec) or ""
            for item in items:
                if kind_field:
                    if kind_match(got, item):
                        return False
                elif got.casefold() == item.casefold():
                    return False
            return True

        return not_equals

    if operator == "~":
        lowered_items = [item.lower() for item in items]

        def contains(rec: Record) -> bool:
            got = (get(rec) or "").lower()
            return any(item in got for item in lowered_items)

        return contains

    if operator == "!~":
        lowered_items = [item.lower() for item in items]

        def not_contains(rec: Record) -> bool:
            got = (get(rec) or "").lower()
            return not any(item in got for item in lowered_items)

        return not_contains

    raise QueryError("string field does not support operator %r" % operator)


def compare_status(operator: str, value: str) -> Predicate:
    """Numeric comparison for HTTP status codes, e.g. ``status>=400``.

    Status is stored as a string, so ``=`` / ``~`` stay textual; ordering
    operators only match records that actually have a numeric status.
    """

    try:
        number = int(value.strip(), 10)
    except ValueError:
        raise QueryError("status comparison needs a number, got %r" % value) from None
    comparisons = {
        ">": lambda got: got > number,
        "<": lambda got: got < number,
        ">=": lambda got: got >= number,
        "<=": lambda got: got <= number,
    }
    compare = comparisons.get(operator)
    if compare is None:
        raise QueryError("status does not support operator %r" % operator)

    def check(rec: Record) -> bool:
        raw = (rec.status or "").strip()
        if not raw.isdigit():
            return False
        return compare(int(raw))

    return check


def compare_int(
    get: Callable[[Record], int], operator: str, value: str
) -> Predicate:
    try:
        number = int(value.strip(), 10)
    except ValueError:
        raise QueryError("invalid number %r" % value) from None
    comparisons = {
        "=": lambda got: got == number,
        "==": lambda got: got == number,
        "!=": lambda got: got != number,
        ">": lambda got: got > number,
        "<": lambda got: got < number,
        ">=": lambda got: got >= number,
        "<=": lambda got: got <= number,
    }
    compare = comparisons.get(operator)
    if compare is None:
        raise QueryError("numeric field does not support operator %r" % operator)
    return lambda rec: compare(get(rec))


def by_index(records: Sequence[Record], index: int) -> Optional[Record]:
    for record in records:
        if record.index == index:
            return record
    return None


def by_theology(records: Sequence[Record], theology: int) -> Optional[Record]:
    for record in records:
        if record.theology == theology:
            return record
    return None
