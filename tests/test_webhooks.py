from __future__ import annotations

import json
from typing import Any

import pytest

import rayacash
from rayacash import _webhook
from tests.fixtures import (
    EVENT_PAYMENT_SUCCEEDED,
    WEBHOOK_OLD_SECRET,
    WEBHOOK_OLD_SIGNATURE,
    WEBHOOK_SECRET,
    WEBHOOK_SIGNATURE,
    WEBHOOK_TEST_BODY,
    WEBHOOK_TEST_TIMESTAMP,
)

T = WEBHOOK_TEST_TIMESTAMP
HEADER = f"t={T},v1={WEBHOOK_SIGNATURE}"
verify = rayacash.WebhookSignature.verify_header


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_webhook, "_now", lambda: float(T))


def test_published_vectors() -> None:
    assert (
        rayacash.WebhookSignature.compute_signature(WEBHOOK_TEST_BODY, WEBHOOK_SECRET, T)
        == WEBHOOK_SIGNATURE
    )
    assert (
        rayacash.WebhookSignature.compute_signature(WEBHOOK_TEST_BODY, WEBHOOK_OLD_SECRET, T)
        == WEBHOOK_OLD_SIGNATURE
    )
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET) is True


def test_the_api_md_vector_with_a_real_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_webhook, "_now", lambda: 2_000_000_000.0)
    # El t del vector es viejo: para probarlo, la doc pide saltear el chequeo de los 5 minutos.
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET, tolerance=None) is True
    with pytest.raises(rayacash.SignatureVerificationError, match="de tu reloj"):
        verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET)


def test_rotation_sends_two_signatures() -> None:
    header = f"t={T},v1={WEBHOOK_SIGNATURE},v1={WEBHOOK_OLD_SIGNATURE}"
    assert verify(WEBHOOK_TEST_BODY, header, WEBHOOK_SECRET)
    assert verify(WEBHOOK_TEST_BODY, header, WEBHOOK_OLD_SECRET)
    with pytest.raises(rayacash.SignatureVerificationError, match="no coincide"):
        verify(WEBHOOK_TEST_BODY, header, "whsec_otro")


@pytest.mark.parametrize(
    "header",
    [
        f"t={T}, v1={WEBHOOK_SIGNATURE}",
        f" v1={WEBHOOK_SIGNATURE} , t={T} ",
        f"t={T},v0=abc,v1={WEBHOOK_SIGNATURE},extra",
        f"t={T},v1={WEBHOOK_SIGNATURE.upper()}",
        f"t=,t={T},v1=no-es-hex,v1={WEBHOOK_SIGNATURE}",
    ],
)
def test_lenient_header_parsing(header: str) -> None:
    assert verify(WEBHOOK_TEST_BODY, header, WEBHOOK_SECRET)


@pytest.mark.parametrize(
    ("header", "message"),
    [
        (None, "Falta el header"),
        ("", "Falta el header"),
        ("   ", "Falta el header"),
        (f"v1={WEBHOOK_SIGNATURE}", "No pudimos leer t"),
        (f"t=abc,v1={WEBHOOK_SIGNATURE}", "No pudimos leer t"),
        (f"t=１７００,v1={WEBHOOK_SIGNATURE}", "No pudimos leer t"),
        (f"t={'9' * 30},v1={WEBHOOK_SIGNATURE}", "No pudimos leer t"),
        (f"t={T}", "no trae firmas v1"),
        (f"t={T},v1=", "no trae firmas v1"),
        (f"t={T},v1={'0' * 64}", "no coincide"),
        (f"t={T + 1},v1={WEBHOOK_SIGNATURE}", "no coincide"),
    ],
)
def test_invalid_headers(header: str | None, message: str) -> None:
    with pytest.raises(rayacash.SignatureVerificationError, match=message) as info:
        verify(WEBHOOK_TEST_BODY, header, WEBHOOK_SECRET)
    assert info.value.sig_header == header
    assert info.value.http_body == WEBHOOK_TEST_BODY.decode()


def test_tampered_body() -> None:
    with pytest.raises(rayacash.SignatureVerificationError, match="body crudo"):
        verify(
            WEBHOOK_TEST_BODY.replace(b"webhook.test", b"payment.succeeded"), HEADER, WEBHOOK_SECRET
        )


@pytest.mark.parametrize("skew", [-300, 300, -1, 1])
def test_tolerance_inside(monkeypatch: pytest.MonkeyPatch, skew: int) -> None:
    monkeypatch.setattr(_webhook, "_now", lambda: float(T + skew))
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET)


@pytest.mark.parametrize("skew", [-301, 301, 3600])
def test_tolerance_is_symmetric(monkeypatch: pytest.MonkeyPatch, skew: int) -> None:
    monkeypatch.setattr(_webhook, "_now", lambda: float(T + skew))
    with pytest.raises(rayacash.SignatureVerificationError, match="300 s"):
        verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET)
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET, tolerance=None)
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET, tolerance=0)
    assert verify(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET, tolerance=4000)


def test_payload_forms() -> None:
    text = WEBHOOK_TEST_BODY.decode()
    assert verify(text, HEADER, WEBHOOK_SECRET)
    assert verify(bytearray(WEBHOOK_TEST_BODY), HEADER, WEBHOOK_SECRET)
    assert verify(memoryview(WEBHOOK_TEST_BODY), HEADER, WEBHOOK_SECRET)
    with pytest.raises(TypeError, match="body crudo"):
        verify({"id": "evt_test"}, HEADER, WEBHOOK_SECRET)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"secret": ""}, ValueError),
        ({"secret": None}, TypeError),
        ({"tolerance": -1}, ValueError),
        ({"tolerance": "300"}, TypeError),
        ({"header": b"t=1,v1=x"}, TypeError),
    ],
)
def test_programming_errors(kwargs: dict[str, object], error: type[Exception]) -> None:
    arguments: dict[str, object] = {
        "header": HEADER,
        "secret": WEBHOOK_SECRET,
        "tolerance": 300,
        **kwargs,
    }
    with pytest.raises(error):
        verify(WEBHOOK_TEST_BODY, **arguments)  # type: ignore[arg-type]


def test_construct_event() -> None:
    body = json.dumps(EVENT_PAYMENT_SUCCEEDED).encode()
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    assert (
        header == f"t={T},v1={rayacash.WebhookSignature.compute_signature(body, WEBHOOK_SECRET, T)}"
    )
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert type(event) is rayacash.Event
    assert event.id == "evt_4mQ8sT2vX7bN1kR5wZ9cH3jL"
    assert event.type == "payment.succeeded"
    assert type(event.data.object) is rayacash.Payment
    assert event.data.object.status == "succeeded"


def test_construct_event_test_and_unknown_types() -> None:
    event = rayacash.Webhook.construct_event(WEBHOOK_TEST_BODY, HEADER, WEBHOOK_SECRET)
    assert event.type == "webhook.test"
    body = json.dumps(
        {
            "id": "evt_x",
            "object": "event",
            "type": "algo.nuevo",
            "data": {"object": {"object": "nuevo"}},
        }
    )
    event = rayacash.Webhook.construct_event(
        body, rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET), WEBHOOK_SECRET
    )
    assert event["type"] == "algo.nuevo"  # un tipo que el SDK todavía no conoce
    assert type(event.data.object) is rayacash.RayaObject


def test_construct_event_rejects_bad_signatures_before_parsing() -> None:
    with pytest.raises(rayacash.SignatureVerificationError):
        rayacash.Webhook.construct_event(b"no es json", HEADER, WEBHOOK_SECRET)


def test_construct_event_needs_a_json_object() -> None:
    body = b"[1, 2]"
    with pytest.raises(ValueError, match="objeto JSON"):
        rayacash.Webhook.construct_event(
            body, rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET), WEBHOOK_SECRET
        )


def test_generate_header_with_explicit_timestamp() -> None:
    header = rayacash.WebhookSignature.generate_header(
        WEBHOOK_TEST_BODY, WEBHOOK_SECRET, timestamp=T
    )
    assert header == HEADER
    bad_timestamps: list[Any] = [-1, True, 1.5]
    for bad in bad_timestamps:
        with pytest.raises(ValueError, match="timestamp"):
            rayacash.WebhookSignature.generate_header(
                WEBHOOK_TEST_BODY, WEBHOOK_SECRET, timestamp=bad
            )
