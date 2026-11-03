"""Filter and expression-engine tests."""

from __future__ import annotations

import pytest

from conftest import make_http_record
from sy4py.errors import QueryError
from sy4py.model import KIND_WEBSOCKET, fill_derived
from sy4py.query import Query, parse_expr


@pytest.fixture()
def loaded(records):
    for record in records:
        fill_derived(record)
    return records


def test_empty_query_keeps_everything(loaded):
    assert len(Query().apply(loaded)) == 4


def test_filter_by_type(loaded):
    assert [r.index for r in Query(type="ws").apply(loaded)] == [2]
    assert [r.index for r in Query(type="http,tcp").apply(loaded)] == [1, 3]
    assert [r.index for r in Query(type="http,websocket").apply(loaded)] == [1, 2]


def test_filter_by_method_is_exact(loaded):
    assert [r.index for r in Query(method="post").apply(loaded)] == [1]
    assert Query(method="POS").apply(loaded) == []


def test_filter_by_host_is_substring(loaded):
    assert [r.index for r in Query(host="example").apply(loaded)] == [1, 2, 3]
    assert [r.index for r in Query(host="api.example.com").apply(loaded)] == [1]


def test_filter_by_status_list(loaded):
    assert [r.index for r in Query(status="101,200").apply(loaded)] == [1, 2]


def test_filter_index_and_theology(loaded):
    assert [r.index for r in Query(index=3).apply(loaded)] == [3]
    assert [r.index for r in Query(theology=1002).apply(loaded)] == [2]


def test_noise_filter_drops_static_assets():
    record = make_http_record(1, url="https://cdn.example.com/app.js")
    fill_derived(record)
    assert Query().apply([record]) == [record]
    assert Query(skip_noise=True).apply([record]) == []


def test_noise_keeps_api_calls():
    record = make_http_record(1, url="https://api.example.com/v1/list")
    fill_derived(record)
    assert Query(skip_noise=True).apply([record]) == [record]


def test_no_status_filter(loaded):
    # TCP/UDP sessions never carry an HTTP status code.
    assert [r.index for r in Query(no_status=True).apply(loaded)] == [3, 4]


def test_limit_and_offset(loaded):
    assert [r.index for r in Query(limit=2).apply(loaded)] == [1, 2]
    assert [r.index for r in Query(offset=2).apply(loaded)] == [3, 4]
    assert [r.index for r in Query(offset=1, limit=1).apply(loaded)] == [2]


def test_expr_or(loaded):
    query = Query(expr="status=101 or status=200")
    assert [r.index for r in query.apply(loaded)] == [1, 2]


def test_expr_and(loaded):
    query = Query(expr="host~api status=200")
    assert [r.index for r in query.apply(loaded)] == [1]


def test_expr_pipe_or(loaded):
    query = Query(expr="type=ws || status=200")
    assert [r.index for r in query.apply(loaded)] == [1, 2]


def test_expr_negation(loaded):
    query = Query(expr="type!=http")
    assert [r.index for r in query.apply(loaded)] == [2, 3, 4]


def test_expr_numeric(loaded):
    assert [r.index for r in Query(expr="index>=3").apply(loaded)] == [3, 4]
    assert [r.index for r in Query(expr="frames>0").apply(loaded)] == [2, 3, 4]


def test_expr_quoted_value(loaded):
    query = Query(expr='url~"login?token"')
    assert [r.index for r in query.apply(loaded)] == [1]


def test_expr_invalid_clause():
    with pytest.raises(QueryError):
        parse_expr("status")


def test_expr_unknown_field():
    with pytest.raises(QueryError, match="unknown field"):
        parse_expr("bogus=1")


def test_expr_invalid_number():
    with pytest.raises(QueryError):
        parse_expr("index=abc")


def test_kind_filter_websocket_alias(loaded):
    assert loaded[1].kind == KIND_WEBSOCKET
    assert [r.index for r in Query(type="websocket").apply(loaded)] == [2]
