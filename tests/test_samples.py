"""Optional parity tests against real captures.

Set ``SY4_SAMPLES`` to a directory containing ``.sy4`` files to run them::

    SY4_SAMPLES=D:\\captures python -m pytest tests/test_samples.py -v

The tests never print bodies or credentials; they only assert structural
invariants so that real traffic stays private.
"""

from __future__ import annotations

import glob
import os

import pytest

from sy4py import open_file
from sy4py.query import Query
from sy4py.stats import summarize

SAMPLES = os.environ.get("SY4_SAMPLES", "")
FILES = sorted(glob.glob(os.path.join(SAMPLES, "*.sy4"))) if SAMPLES else []

pytestmark = pytest.mark.skipif(
    not FILES, reason="set SY4_SAMPLES to a directory with .sy4 files"
)


@pytest.mark.parametrize("path", FILES, ids=[os.path.basename(p) for p in FILES])
def test_every_sample_parses(path):
    archive = open_file(path)
    assert archive.header_count >= 0
    assert len(archive) > 0
    assert [record.index for record in archive] == list(
        range(1, len(archive) + 1)
    )
    for record in archive:
        assert record.kind in ("http", "websocket", "tcp", "udp")
        if record.http is not None:
            assert record.http.request.method == record.method or record.kind == (
                "websocket"
            )
            assert record.http.response.code == record.status


@pytest.mark.parametrize("path", FILES, ids=[os.path.basename(p) for p in FILES])
def test_stats_match_record_count(path):
    archive = open_file(path)
    stats = summarize(archive.records)
    assert stats.total == len(archive)
    assert stats.http + stats.websocket + stats.tcp + stats.udp == stats.total
    assert sum(row.count for row in stats.by_type) == stats.total


@pytest.mark.parametrize("path", FILES, ids=[os.path.basename(p) for p in FILES])
def test_noise_filter_is_a_subset(path):
    archive = open_file(path)
    filtered = Query(skip_noise=True).apply(archive.records)
    assert len(filtered) <= len(archive)
    assert all(record.status != "304" for record in filtered)
