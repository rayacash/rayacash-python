from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from rayacash._encoding import (
    canonical_amount,
    dumps,
    encode_body,
    encode_query,
    path_id,
    validate_idempotency_key,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1500, "1500"),
        (1500.5, "1500.5"),
        (1500.1, "1500.1"),
        (25000.50, "25000.5"),
        (Decimal("1500.50"), "1500.5"),
        (Decimal("1500.00"), "1500"),
        (Decimal("1E+3"), "1000"),
        (Decimal("0.10"), "0.1"),
        ("1500.50", "1500.5"),
        (" 25 ", "25"),
        ("1.5e3", "1500"),
        (0.1 + 0.2, "0.30000000000000004"),  # sin redondear: la API lo rechaza
        (Decimal("1500.505"), "1500.505"),
    ],
)
def test_amounts_travel_as_canonical_json_numbers(value: Any, expected: str) -> None:
    assert dumps({"amount": canonical_amount(value)}) == '{"amount":' + expected + "}"


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        (None, TypeError),
        ([1500], TypeError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (Decimal("NaN"), ValueError),
        (Decimal("-Infinity"), ValueError),
        ("abc", ValueError),
        ("1.500,50", ValueError),
        ("Infinity", ValueError),
        ("", ValueError),
    ],
)
def test_invalid_amounts_fail_before_sending(value: Any, error: type[Exception]) -> None:
    with pytest.raises(error, match="amount"):
        canonical_amount(value)


def test_dumps_handles_every_json_type() -> None:
    value = {
        "s": "ñandú «hola»",
        "i": 1,
        "f": 1.25,
        "d": Decimal("2.50"),
        "b": True,
        "n": None,
        "l": [1, False, ("x",)],
        "o": {"k": "v"},
    }
    assert dumps(value) == (
        '{"s":"\\u00f1and\\u00fa \\u00abhola\\u00bb","i":1,"f":1.25,"d":2.5,"b":true,'
        '"n":null,"l":[1,false,["x"]],"o":{"k":"v"}}'
    )


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ({1: "x"}, TypeError),
        ({"x": object()}, TypeError),
        ({"x": float("nan")}, ValueError),
        ({"x": Decimal("sNaN")}, ValueError),
    ],
)
def test_dumps_rejects_what_json_cannot_carry(value: Any, error: type[Exception]) -> None:
    with pytest.raises(error):
        dumps(value)


def test_encode_body_drops_only_top_level_none() -> None:
    body = encode_body({"amount": Decimal("15000"), "description": None, "metadata": {"a": None}})
    assert body == b'{"amount":15000,"metadata":{"a":null}}'


def test_encode_query() -> None:
    gte = datetime(2026, 10, 23, tzinfo=timezone(timedelta(hours=-3)))
    query = encode_query({"direction": "inbound", "status": None, "created_gte": gte, "limit": 100})
    assert query == {
        "direction": "inbound",
        "created_gte": "2026-10-23T00:00:00-03:00",
        "limit": "100",
    }


def test_encode_query_requires_timezone() -> None:
    with pytest.raises(ValueError, match="created_lt necesita zona horaria"):
        encode_query({"created_lt": datetime(2026, 10, 24)})


@pytest.mark.parametrize("value", [True, 1.5, object()])
def test_encode_query_rejects_other_types(value: Any) -> None:
    with pytest.raises(TypeError, match="limit"):
        encode_query({"limit": value})


def test_path_id_encodes_everything() -> None:
    assert path_id("payment_id", "a/b c?") == "a%2Fb%20c%3F"
    payment_id = "c2a7e5d1-9b34-4f0a-8e62-71d5b3c9a0f8"
    assert path_id("payment_id", payment_id) == payment_id


@pytest.mark.parametrize(
    ("value", "error"), [("", ValueError), ("  ", ValueError), (123, TypeError), (None, TypeError)]
)
def test_path_id_rejects_empty_ids(value: Any, error: type[Exception]) -> None:
    with pytest.raises(error, match="payment_id"):
        path_id("payment_id", value)


@pytest.mark.parametrize("key", ["9b2f6c4e-1d3a-4e8b-a5c7-0f9e8d7c6b5a", "x", "~" * 255, "!#$%"])
def test_valid_idempotency_keys(key: str) -> None:
    assert validate_idempotency_key(key) == key


@pytest.mark.parametrize("key", ["", "a b", "ñ", "x" * 256, "tab\there", "line\n"])
def test_invalid_idempotency_keys(key: str) -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        validate_idempotency_key(key)


def test_idempotency_key_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="idempotency_key"):
        validate_idempotency_key(123)
