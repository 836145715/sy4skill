"""Exception hierarchy for sy4py."""

from __future__ import annotations


class Sy4Error(Exception):
    """Base class for every error raised by sy4py."""


class DecodeError(Sy4Error):
    """The byte stream is not a valid .sy4 archive (or is truncated)."""


class UsageError(Sy4Error):
    """The caller passed invalid arguments."""


class QueryError(Sy4Error):
    """The filter expression could not be parsed."""
