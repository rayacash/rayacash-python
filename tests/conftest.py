from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

import rayacash
from rayacash import _global, _retry
from tests.helpers import Caller, MockAPI

_GLOBAL_DEFAULTS = {
    name: getattr(rayacash, name)
    for name in (
        "api_key",
        "api_base",
        "max_network_retries",
        "timeout",
        "http_client",
        "async_http_client",
        "app_info",
        "log",
    )
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ningún test puede llamar a la API real: no hay sandbox y cada request mueve plata."""

    def deny(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Los tests del SDK nunca salen a la red: usá MockAPI.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny)


@pytest.fixture(autouse=True)
def _isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Sin claves del entorno de quien corre los tests y con los globals de fábrica."""
    monkeypatch.delenv("RAYA_SECRET_KEY", raising=False)
    monkeypatch.setattr("rayacash._util.RAYA_LOG", None)
    for name, value in _GLOBAL_DEFAULTS.items():
        monkeypatch.setattr(rayacash, name, value)
    _global.reset()
    yield
    _global.reset()


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Las esperas de los reintentos, sin dormir. El jitter queda fijo en el máximo."""
    recorded: list[float] = []

    async def sleep_async(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(_retry, "sleep", recorded.append)
    monkeypatch.setattr(_retry, "sleep_async", sleep_async)
    monkeypatch.setattr(_retry, "_jitter", lambda: 1.0)
    return recorded


@pytest.fixture
def api() -> MockAPI:
    return MockAPI()


@pytest.fixture
def client(api: MockAPI) -> Iterator[rayacash.RayaClient]:
    raya = api.client()
    yield raya
    raya.close()


@pytest.fixture(params=["sync", "async"])
def call(request: pytest.FixtureRequest) -> Caller:
    return Caller(request.param)
