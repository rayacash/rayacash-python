from __future__ import annotations

import asyncio

import httpx

import rayacash
from rayacash import _retry
from rayacash._requestor import HTTPClientManager

# Los originales, antes de que el fixture `sleeps` los reemplace.
REAL_SLEEP = _retry.sleep
REAL_SLEEP_ASYNC = _retry.sleep_async
REAL_JITTER = _retry._jitter


def test_real_sleep_and_jitter() -> None:
    REAL_SLEEP(0)
    asyncio.run(REAL_SLEEP_ASYNC(0))
    assert all(0.0 <= REAL_JITTER() < 1.0 for _ in range(100))


def test_http_client_manager_builds_real_clients_lazily() -> None:
    manager = HTTPClientManager()
    sync_client = manager.sync_client()
    assert isinstance(sync_client, httpx.Client)
    assert sync_client.follow_redirects is False
    assert manager.sync_client() is sync_client

    async def build() -> httpx.AsyncClient:
        return manager.async_client()

    async_client = asyncio.run(build())
    assert isinstance(async_client, httpx.AsyncClient)
    asyncio.run(manager.aclose())
    assert sync_client.is_closed
    assert async_client.is_closed
    manager.close()  # cerrar dos veces no falla


def test_response_repr() -> None:
    response = rayacash.RayaResponse(
        http_status=200,
        headers=httpx.Headers({"Raya-Request-Id": "req_x"}),
        body="{}",
        data={},
        idempotency_key=None,
    )
    assert repr(response) == "<RayaResponse http_status=200 request_id='req_x'>"
