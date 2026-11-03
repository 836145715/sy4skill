"""Noise detection: drop CDN/static/telemetry records by default."""

from __future__ import annotations

from typing import List

from .model import Record

NOISE_HOST_BITS: List[str] = [
    "cdn",
    "storeimages",
    "alipayobjects",
    "securemetrics",
    "mmstat",
    "googletagmanager",
    "doubleclick",
    "beacon.qq.com",
    "content-autofill.googleapis.com",
    "optimizationguide-pa.googleapis.com",
    "passwordsleakcheck-pa.googleapis.com",
    "fonts",
]

NOISE_EXTENSIONS: List[str] = [
    ".js",
    ".css",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".webm",
    ".m4s",
]


def is_noise(record: Record) -> bool:
    """Heuristic used by ``--noise`` to hide static assets and telemetry."""

    if record is None:
        return False
    if record.status == "304":
        return True

    host = (record.host or "").lower()
    if any(bit in host for bit in NOISE_HOST_BITS):
        return True

    path = (record.path or "").lower() or path_from_url(record.url or "")
    if path.endswith("/"):
        path = path[:-1]
    extension = _extension(path)
    return bool(extension) and extension in NOISE_EXTENSIONS


def path_from_url(raw: str) -> str:
    index = raw.find("://")
    if index >= 0:
        raw = raw[index + 3 :]
    slash = raw.find("/")
    if slash < 0:
        return ""
    path = raw[slash:]
    query = path.find("?")
    if query >= 0:
        path = path[:query]
    return path


def _extension(path: str) -> str:
    slash = path.rfind("/")
    dot = path.rfind(".")
    if dot <= slash:
        return ""
    return path[dot:]
