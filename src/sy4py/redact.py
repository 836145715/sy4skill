"""Redaction of credentials before printing or exporting records."""

from __future__ import annotations

import copy
from typing import Dict, List

from .model import Record

SENSITIVE_HEADERS = {
    "cookie",
    "set-cookie",
    "authorization",
    "proxy-authorization",
}

#: Query parameter names whose values are masked by :func:`redact_url`.
SENSITIVE_PARAMS = {
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "session",
    "sessionid",
    "session_id",
    "jsessionid",
    "phpsessid",
    "auth",
    "authorization",
    "ticket",
    "sign",
    "signature",
    "secret",
    "password",
    "passwd",
    "pwd",
    "apikey",
    "api_key",
    "appkey",
    "accesskey",
    "access_key",
    "openid",
}

MASK = "***"


def is_sensitive_header(name: str) -> bool:
    lowered = (name or "").lower()
    if lowered in SENSITIVE_HEADERS:
        return True
    return "token" in lowered or "session" in lowered


def redact_header(header: Dict[str, List[str]]) -> Dict[str, List[str]]:
    if not header:
        return {}
    return {
        key: [MASK] * len(values) if is_sensitive_header(key) else list(values)
        for key, values in header.items()
    }


def redact_url(url: str) -> str:
    """Mask values of well-known credential query parameters."""

    if not url:
        return url
    head, sep, tail = url.partition("?")
    if not sep:
        return url
    base, hash_sep, fragment = tail.partition("#")
    params = []
    for chunk in base.split("&"):
        if not chunk:
            continue
        name, eq, _value = chunk.partition("=")
        if eq and name.lower() in SENSITIVE_PARAMS:
            params.append("%s=%s" % (name, MASK))
        else:
            params.append(chunk)
    rebuilt = head + "?" + "&".join(params)
    if hash_sep:
        rebuilt += "#" + fragment
    return rebuilt


def redact_record(record: Record) -> Record:
    """Deep-copy ``record`` with credential headers and query values masked."""

    clone = copy.deepcopy(record)
    if clone.http is not None:
        clone.http.request.header = redact_header(clone.http.request.header)
        clone.http.response.header = redact_header(clone.http.response.header)
        clone.http.request.url = redact_url(clone.http.request.url)
        clone.url = redact_url(clone.url)
        clone.query = clone.http.request.url.partition("?")[2]
    return clone
