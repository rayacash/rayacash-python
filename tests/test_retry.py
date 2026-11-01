from __future__ import annotations

import email.utils
import time

import pytest

from rayacash import _retry
from rayacash._retry import backoff_delay, parse_retry_after, retry_delay, should_retry_response


@pytest.mark.parametrize(
    ("header", "expected"),
    [(None, None), ("", None), ("  ", None), ("2", 2.0), (" 5 ", 5.0), ("abc", None), ("-1", None)],
)
def test_parse_retry_after_seconds(header: str | None, expected: float | None) -> None:
    assert parse_retry_after(header) == expected


def test_parse_retry_after_http_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)
    future = email.utils.formatdate(1_700_000_030, usegmt=True)
    past = email.utils.formatdate(1_699_999_000, usegmt=True)
    assert parse_retry_after(future) == pytest.approx(30.0)
    assert parse_retry_after(past) == 0.0
    naive = email.utils.formatdate(1_700_000_010)[:-6]  # sin zona: se toma UTC
    assert parse_retry_after(naive) == pytest.approx(10.0)


def test_backoff_grows_exponentially_with_a_cap() -> None:
    # El fixture `sleeps` fija el jitter en el máximo (1.0).
    assert [backoff_delay(n) for n in range(1, 7)] == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]


def test_backoff_jitter_halves_at_most(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_retry, "_jitter", lambda: 0.0)
    assert backoff_delay(3) == 1.0


def test_retry_after_is_a_floor() -> None:
    assert retry_delay(1, 5.0) == 5.0
    assert retry_delay(4, 2.0) == 4.0
    assert retry_delay(1, None) == 0.5


@pytest.mark.parametrize(
    ("status", "code", "retry_after", "expected"),
    [
        (409, "IDEMPOTENCY_KEY_IN_USE", 2.0, True),
        (409, "IDEMPOTENCY_KEY_REUSED", None, False),
        (409, "PAYMENT_NOT_REFUNDABLE", None, False),
        (429, "RATE_LIMITED", 30.0, True),
        (429, "RATE_LIMITED", 60.0, True),
        (429, "RATE_LIMITED", 61.0, False),
        (429, "RATE_LIMITED", None, True),
        (408, "INTERNAL_ERROR", None, True),
        (500, "INTERNAL_ERROR", None, True),
        (502, "INTERNAL_ERROR", None, True),
        (503, "BANK_UNAVAILABLE", None, True),
        (503, "BANK_UNAVAILABLE", 3600.0, False),
        (503, "CVU_UNAVAILABLE", 5.0, True),
        (503, "TEMPORARILY_UNAVAILABLE", 5.0, True),
        (503, "API_UNAVAILABLE", None, False),
        (504, "INTERNAL_ERROR", None, True),
        (400, "PARAMETER_INVALID", None, False),
        (401, "API_KEY_INVALID", None, False),
        (404, "NOT_FOUND", None, False),
        (422, "INSUFFICIENT_BALANCE", None, False),
        (302, "INVALID_RESPONSE", None, False),
    ],
)
def test_retry_policy(status: int, code: str, retry_after: float | None, expected: bool) -> None:
    assert should_retry_response(status, code, retry_after) is expected
