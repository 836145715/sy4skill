"""Low-level binary reader for the SunnyNetV4 ``.sy4`` container.

The format is a flat, big-endian TLV stream:

* ``int``    -> 8 bytes, unsigned big endian
* ``bool``   -> 1 byte, ``0`` is false
* ``string`` -> ``int`` byte length + raw bytes (UTF-8 in practice)
* ``body``   -> ``int`` byte length + raw bytes
* ``header`` -> ``int`` entry count, then repeated
                ``string key`` + ``int`` value count + N ``string`` values
* array      -> ``int`` item count, then N ``int`` values

A file starts with an ``int`` record count, followed by records whose first
byte is the record type (``b"1"`` HTTP, ``b"2"`` TCP, ``b"3"`` UDP).
"""

from __future__ import annotations

import struct
from typing import Dict, List

from .errors import DecodeError

#: Hard limits, mirrored from the reference Go implementation, used to fail
#: fast on corrupt data instead of allocating gigabytes.
MAX_RECORDS = 5_000_000
MAX_FIELD = 256 << 20

_U64 = struct.Struct(">Q")


class Reader:
    """Cursor over an in-memory ``.sy4`` byte string."""

    __slots__ = ("_data", "_pos", "_size")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0
        self._size = len(data)

    def __len__(self) -> int:
        return self._size

    @property
    def offset(self) -> int:
        """Current read offset, useful for error messages."""

        return self._pos

    def eof(self) -> bool:
        return self._pos >= self._size

    def _take(self, n: int) -> bytes:
        if n < 0:
            raise DecodeError("negative length %d" % n)
        end = self._pos + n
        if end > self._size:
            raise DecodeError(
                "unexpected end of data at offset %d: need %d byte(s), %d left"
                % (self._pos, n, self._size - self._pos)
            )
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def read_int(self) -> int:
        return _U64.unpack(self._take(8))[0]

    def read_bool(self) -> bool:
        return self._take(1)[0] != 0

    def read_type(self) -> str:
        return self._take(1).decode("ascii", "replace")

    def read_string(self) -> str:
        n = self.read_int()
        if n <= 0:
            return ""
        if n > MAX_FIELD:
            raise DecodeError("string field too long: %d bytes" % n)
        return self._take(n).decode("utf-8", "replace")

    def read_body(self) -> bytes:
        n = self.read_int()
        if n <= 0:
            return b""
        if n > MAX_FIELD:
            raise DecodeError("body field too long: %d bytes" % n)
        return self._take(n)

    def read_int_array(self) -> List[int]:
        n = self.read_int()
        if n < 0 or n > MAX_RECORDS:
            raise DecodeError("suspicious array length %d" % n)
        read = self.read_int
        return [read() for _ in range(n)]

    def read_header(self) -> Dict[str, List[str]]:
        n = self.read_int()
        if n < 0 or n > MAX_RECORDS:
            raise DecodeError("suspicious header entry count %d" % n)
        header: Dict[str, List[str]] = {}
        for _ in range(n):
            key = self.read_string()
            count = self.read_int()
            if count < 0 or count > MAX_RECORDS:
                raise DecodeError("suspicious header value count %d" % count)
            header[key] = [self.read_string() for _ in range(count)]
        return header
