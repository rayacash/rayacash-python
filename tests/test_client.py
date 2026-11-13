from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import pytest

import rayacash
from rayacash._requestor import HTTPClientManager
from tests.fixtures import (
    BALANCE,
    EVENT_PAYMENT_SUCCEEDED,
    PAYMENT_REFUNDED,
    TRANSFER_LIST,
    WEBHOOK_SECRET,
)
from tests.fixtures_apps import ACCESS_TOKEN, SANDBOX_ACCESS_TOKEN, USER
from tests.fixtures_sandbox import SANDBOX_KEY
from tests.helpers import OTHER_KEY, TEST_KEY, Caller, MockAPI


def test_key_from_argument(api: MockAPI) -> None:
    api.add(200, BALANCE)
    api.client(TEST_KEY).balance.retrieve()
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"


def test_key_from_environment(api: MockAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAYA_SECRET_KEY", OTHER_KEY)
    api.add(200, BALANCE)
    api.client(None).balance.retrieve()
    assert api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"


def test_missing_key_fails_before_any_request(api: MockAPI) -> None:
    client = api.client(None)
    with pytest.raises(rayacash.AuthenticationError) as info:
        client.balance.retrieve()
    assert info.value.code == "API_KEY_MISSING"
    assert "RAYA_SECRET_KEY" in info.value.message
    assert api.requests == []


@pytest.mark.parametrize(
    ("key", "code"),
    [
        ("", "API_KEY_MISSING"),
        ("   ", "API_KEY_MISSING"),
        ("raya_pk_live_" + "a" * 48, "API_KEY_PUBLISHABLE_NOT_ALLOWED"),
        (TEST_KEY + " ", "API_KEY_INVALID"),
        ("raya_sk_live_ñ", "API_KEY_INVALID"),
        (TEST_KEY + "\n", "API_KEY_INVALID"),
    ],
)
def test_invalid_keys_fail_at_construction(key: str, code: str) -> None:
    with pytest.raises(rayacash.AuthenticationError) as info:
        rayacash.RayaClient(key)
    assert info.value.code == code


def test_key_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        rayacash.RayaClient(123)  # type: ignore[arg-type]


def test_per_request_key(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, BALANCE)
    client.balance.retrieve(options={"api_key": OTHER_KEY})
    assert api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    with pytest.raises(rayacash.AuthenticationError) as info:
        client.balance.retrieve(options={"api_key": "raya_pk_live_x"})
    assert info.value.code == "API_KEY_PUBLISHABLE_NOT_ALLOWED"
    assert len(api.requests) == 1


def test_unknown_options_are_rejected(client: rayacash.RayaClient) -> None:
    bad_options: Any = {"idempotency_key": "x"}
    with pytest.raises(TypeError, match="idempotency_key"):
        client.balance.retrieve(options=bad_options)
    with pytest.raises(TypeError):
        client.balance.retrieve(options="x")  # type: ignore[arg-type]


def test_repr_never_shows_the_key() -> None:
    client = rayacash.RayaClient(TEST_KEY)
    assert (
        repr(client) == "<RayaClient api_base='https://api.raya.cash' api_key='raya_sk_live_…IJKL'>"
    )
    assert TEST_KEY not in repr(client)
    assert (
        repr(rayacash.RayaClient()) == "<RayaClient api_base='https://api.raya.cash' api_key=None>"
    )
    assert "…" in repr(rayacash.RayaClient("otra_clave_cualquiera_larga"))
    assert repr(rayacash.RayaClient("corta")).endswith("api_key='…'>")


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://api.raya.cash/", "https://api.raya.cash"),
        ("https://proxy.example.com/raya", "https://proxy.example.com/raya"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
        ("http://[::1]:8000", "http://[::1]:8000"),
        # Una query o un fragmento vacíos cuentan como ausentes: antes quedaban en la base y
        # las requests iban a /?/v1/… o a /.
        ("https://api.raya.cash?", "https://api.raya.cash"),
        ("https://api.raya.cash#", "https://api.raya.cash"),
        ("https://api.raya.cash/?#", "https://api.raya.cash"),
        ("http://localhost:8000/raya/?", "http://localhost:8000/raya"),
    ],
)
def test_valid_api_base(api: MockAPI, base: str, expected: str) -> None:
    api.add(200, BALANCE)
    client = api.client(api_base=base)
    client.balance.retrieve()
    assert str(api.last.url) == expected + "/v1/balance"
    assert f"api_base={expected!r}" in repr(client)


@pytest.mark.parametrize(
    "base",
    [
        "http://api.raya.cash",
        "ftp://x",
        "api.raya.cash",
        "https://",
        "https://x?y=1",
        "https://x#y",
        "https://x?#y",
        "https://x#?",
        "https://u:p@x",
    ],
)
def test_invalid_api_base(base: str) -> None:
    with pytest.raises(ValueError, match="api_base"):
        rayacash.RayaClient(TEST_KEY, api_base=base)


def test_api_base_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        rayacash.RayaClient(TEST_KEY, api_base=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"timeout": 0}, ValueError),
        ({"timeout": float("inf")}, ValueError),
        ({"timeout": "60"}, TypeError),
        ({"timeout": True}, TypeError),
        ({"max_network_retries": -1}, ValueError),
        ({"max_network_retries": 1.5}, TypeError),
        ({"http_client": object()}, TypeError),
        ({"async_http_client": httpx.Client()}, TypeError),
        ({"app_info": {"name": ""}}, ValueError),
        ({"app_info": {"name": "x", "otra": "y"}}, ValueError),
        ({"app_info": {"name": "x", "version": 1}}, TypeError),
        ({"app_info": {"name": "plugin\r\nX-Inyectado: 1"}}, ValueError),
        ({"app_info": "x"}, TypeError),
    ],
)
def test_invalid_client_options(kwargs: dict[str, Any], error: type[Exception]) -> None:
    with pytest.raises(error):
        rayacash.RayaClient(TEST_KEY, **kwargs)


def test_timeouts(api: MockAPI) -> None:
    api.add(200, BALANCE)
    api.add(200, BALANCE)
    api.add(200, BALANCE)
    client = api.client()
    client.balance.retrieve()
    assert api.last.extensions["timeout"] == {
        "connect": 10.0,
        "read": 65.0,
        "write": 65.0,
        "pool": 65.0,
    }
    client.balance.retrieve(options={"timeout": 5})
    assert api.last.extensions["timeout"] == {
        "connect": 5.0,
        "read": 5.0,
        "write": 5.0,
        "pool": 5.0,
    }
    api.client(timeout=httpx.Timeout(90.0)).balance.retrieve()
    assert api.last.extensions["timeout"]["read"] == 90.0


def test_default_headers(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, BALANCE)
    client.balance.retrieve()
    headers = api.last.headers
    assert headers["accept"] == "application/json"
    assert re.fullmatch(
        r"rayacash-python/\d+\.\d+\.\d+ Python/\d+\.\d+\.\d+\S* httpx/\S+", headers["user-agent"]
    )
    assert "content-type" not in headers
    assert "idempotency-key" not in headers


def test_app_info_goes_in_the_user_agent(api: MockAPI) -> None:
    api.add(200, BALANCE)
    api.add(200, BALANCE)
    info: rayacash.AppInfo = {
        "name": "mi-plugin",
        "version": "1.2.0",
        "url": "https://plugin.example",
    }
    api.client(app_info=info).balance.retrieve()
    assert api.last.headers["user-agent"].endswith(" mi-plugin/1.2.0 (https://plugin.example)")
    api.client(app_info={"name": "solo-nombre"}).balance.retrieve()
    assert api.last.headers["user-agent"].endswith(" solo-nombre")


def test_context_manager_closes_only_owned_clients(
    monkeypatch: pytest.MonkeyPatch, api: MockAPI
) -> None:
    owned: list[httpx.Client] = []

    def new_client(self: HTTPClientManager) -> httpx.Client:
        owned.append(api.sync_client())
        return owned[-1]

    monkeypatch.setattr(HTTPClientManager, "_new_sync_client", new_client)
    api.add(200, BALANCE)
    with rayacash.RayaClient(TEST_KEY) as client:
        client.balance.retrieve()
    assert owned[0].is_closed

    user_client = api.sync_client()
    api.add(200, BALANCE)
    with rayacash.RayaClient(TEST_KEY, http_client=user_client) as client:
        client.balance.retrieve()
    assert not user_client.is_closed


def test_async_context_manager_closes_owned_clients(
    monkeypatch: pytest.MonkeyPatch, api: MockAPI
) -> None:
    owned: list[httpx.AsyncClient] = []

    def new_client(self: HTTPClientManager) -> httpx.AsyncClient:
        owned.append(api.async_client())
        return owned[-1]

    monkeypatch.setattr(HTTPClientManager, "_new_async_client", new_client)

    async def main() -> None:
        async with rayacash.RayaClient(TEST_KEY) as client:
            api.add(200, BALANCE)
            await client.balance.retrieve_async()

    asyncio.run(main())
    assert owned[0].is_closed


def test_owned_async_client_follows_the_event_loop(
    monkeypatch: pytest.MonkeyPatch, api: MockAPI
) -> None:
    created: list[httpx.AsyncClient] = []

    def new_client(self: HTTPClientManager) -> httpx.AsyncClient:
        created.append(api.async_client())
        return created[-1]

    monkeypatch.setattr(HTTPClientManager, "_new_async_client", new_client)
    client = rayacash.RayaClient(TEST_KEY)

    async def two_calls() -> None:
        api.add(200, BALANCE)
        api.add(200, BALANCE)
        await client.balance.retrieve_async()
        await client.balance.retrieve_async()

    asyncio.run(two_calls())
    assert len(created) == 1  # mismo loop, mismo cliente
    asyncio.run(two_calls())
    assert len(created) == 2  # otro loop (otro asyncio.run), otro cliente
    asyncio.run(client.aclose())


def test_raw_request(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, {"object": "nuevo", "x": 1})
    obj = client.raw_request("get", "/v1/algo", params={"limit": 5, "skip": None})
    assert type(obj) is rayacash.RayaObject
    assert obj["x"] == 1
    assert api.last.method == "GET"
    assert str(api.last.url) == "https://api.raya.cash/v1/algo?limit=5"

    api.add(201, PAYMENT_REFUNDED)
    payment = client.raw_request("post", "/v1/algo", body={"a": 1})
    assert type(payment) is rayacash.Payment
    assert api.last_json() == {"a": 1}
    assert api.last.headers["content-type"] == "application/json"
    assert payment.last_response is not None
    assert api.last.headers["idempotency-key"] == payment.last_response.idempotency_key


def test_raw_request_async_lists_can_paginate(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, TRANSFER_LIST)
    page = asyncio.run(client.raw_request_async("get", "/v1/transfers", params={"limit": 2}))
    assert isinstance(page, rayacash.ListObject)
    api.add(200, {**TRANSFER_LIST, "has_more": False, "next_cursor": None})
    page.next_page()
    assert api.last.url.params["cursor"] == TRANSFER_LIST["next_cursor"]
    assert api.last.url.params["limit"] == "2"


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "message"),
    [
        ("put", "/v1/balance", {}, "GET y POST"),
        ("get", "v1/balance", {}, "empezar con /"),
        ("get", "/v1/balance", {"idempotency_key": "x"}, "solo va en los POST"),
    ],
)
def test_raw_request_validation(
    client: rayacash.RayaClient, method: str, path: str, kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        client.raw_request(method, path, **kwargs)


@pytest.mark.parametrize("path", ["/v1/algo?x=1", "/v1/algo#x", "/v1/algo?", "/v1/algo/#"])
def test_raw_request_paths_go_without_a_query(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, path: str
) -> None:
    # La query va en params: la de la ruta se perdía al pasar params y en las páginas siguientes.
    with pytest.raises(ValueError, match=r"^La ruta va sin query \(usá params\)\.$"):
        call(client, "raw_request", "get", path, params={"limit": 2})
    assert api.requests == []


@pytest.mark.parametrize(
    "path", ["/v1/algo\\x", "/v1/algo\tx", "/v1/algo\nx", "/v1/algo\rx", "/v1/\x00", "/v1/\x7f"]
)
def test_raw_request_paths_go_without_backslashes_or_controls(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, path: str
) -> None:
    # Como en Node.js y PHP. Los de control eran un httpx.InvalidURL (no un ValueError), y \ viaja
    # tal cual, pero fetch la convierte en / y un proxy puede hacer lo mismo.
    with pytest.raises(
        ValueError, match=r"^La ruta va sin \\ ni caracteres de control \(codificá los ids\)\.$"
    ):
        call(client, "raw_request", "get", path)
    assert api.requests == []


def test_raw_request_encodes_spaces_and_non_ascii(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, {"object": "nuevo"})
    client.raw_request("get", "/v1/algo nuevo/ñandú")
    assert api.last.url.raw_path == b"/v1/algo%20nuevo/%C3%B1and%C3%BA"


def test_construct_event_binds_the_client(client: rayacash.RayaClient, api: MockAPI) -> None:
    import json as _json

    body = _json.dumps(EVENT_PAYMENT_SUCCEEDED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = client.construct_event(body, header, WEBHOOK_SECRET)
    payment = event.data.object
    assert isinstance(payment, rayacash.Payment)
    api.add(200, PAYMENT_REFUNDED)
    refunded = payment.refund()
    assert refunded.status == "refunded"
    assert api.last.url.path == f"/v1/payments/{payment.id}/refund"


# --- El access_token de una cuenta conectada vale como api_key ------------------------------------


def test_access_token_as_api_key(api: MockAPI) -> None:
    api.add(200, USER)
    api.client(ACCESS_TOKEN).users.retrieve("me")
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_access_token_from_environment_and_per_request(
    api: MockAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAYA_SECRET_KEY", ACCESS_TOKEN)
    api.add(200, USER)
    api.client(None).users.retrieve("me")
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
    api.add(200, USER)
    api.client(TEST_KEY).users.retrieve("me", options={"api_key": ACCESS_TOKEN})
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_repr_masks_the_access_token() -> None:
    client = rayacash.RayaClient(ACCESS_TOKEN)
    assert (
        repr(client) == "<RayaClient api_base='https://api.raya.cash' api_key='raya_at_live_…fG9h'>"
    )
    assert ACCESS_TOKEN not in repr(client)


def test_sandbox_access_token_is_a_key_masked_with_its_prefix(api: MockAPI) -> None:
    # El access_token de un usuario de prueba de un sandbox vale como el de una cuenta conectada,
    # y la máscara conserva su prefijo y sus últimos 4.
    api.add(200, USER)
    client = api.client(SANDBOX_ACCESS_TOKEN)
    client.users.retrieve("me")
    assert api.last.headers["authorization"] == f"Bearer {SANDBOX_ACCESS_TOKEN}"
    assert (
        repr(client) == "<RayaClient api_base='https://api.raya.cash' api_key='raya_at_test_…L0sA'>"
    )
    assert SANDBOX_ACCESS_TOKEN not in repr(client)
    # Con 8 caracteres o menos después del prefijo, solo el prefijo.
    assert repr(rayacash.RayaClient("raya_at_test_12345678")).endswith("api_key='raya_at_test_…'>")


def test_sandbox_secret_key_is_a_key_masked_with_its_prefix(api: MockAPI) -> None:
    # La clave secreta de prueba de un sandbox es el par de la real: va igual, en Authorization,
    # y la máscara conserva su prefijo y sus últimos 4.
    api.add(200, BALANCE)
    client = api.client(SANDBOX_KEY)
    client.balance.retrieve()
    assert api.last.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    assert (
        repr(client) == "<RayaClient api_base='https://api.raya.cash' api_key='raya_sk_test_…IJKL'>"
    )
    assert SANDBOX_KEY not in repr(client)
    assert repr(rayacash.RayaClient("raya_sk_test_12345678")).endswith("api_key='raya_sk_test_…'>")
    # La pública de prueba se rechaza antes de mandar nada, como la real.
    with pytest.raises(rayacash.AuthenticationError) as info:
        rayacash.RayaClient("raya_pk_test_" + "a" * 48)
    assert info.value.code == "API_KEY_PUBLISHABLE_NOT_ALLOWED"
    assert len(api.requests) == 1


@pytest.mark.parametrize(
    ("key", "code", "mentions"),
    [
        ("", "API_KEY_MISSING", ("raya_sk_live_", "raya_at_live_", "RAYA_SECRET_KEY")),
        (
            "raya_pk_live_" + "a" * 48,
            "API_KEY_PUBLISHABLE_NOT_ALLOWED",
            ("raya_sk_live_", "raya_at_live_"),
        ),
        (ACCESS_TOKEN + " ", "API_KEY_INVALID", ("Developers › API Keys", "access_token")),
        (ACCESS_TOKEN + "\n", "API_KEY_INVALID", ("access_token",)),
    ],
)
def test_key_messages_name_both_credentials(key: str, code: str, mentions: tuple[str, ...]) -> None:
    with pytest.raises(rayacash.AuthenticationError) as info:
        rayacash.RayaClient(key)
    assert info.value.code == code
    for text in mentions:
        assert text in info.value.message
