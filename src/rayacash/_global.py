"""El estilo global: ``rayacash.api_key = …`` y ``rayacash.Payment.create(...)``.

La configuración se lee de los globals del módulo en cada request, así que cambiarla entre
llamadas surte efecto enseguida.
"""

from __future__ import annotations

import os
import threading

import httpx

from rayacash._requestor import (
    APIRequestor,
    HTTPClientManager,
    RequestorConfig,
    normalize_api_base,
    to_timeout,
    validate_max_network_retries,
)
from rayacash._util import user_agent, validate_app_info


class _GlobalConfig(RequestorConfig):
    def api_key(self) -> str | None:
        import rayacash

        if rayacash.api_key is not None:
            return rayacash.api_key
        return os.environ.get("RAYA_SECRET_KEY") or None

    def api_base(self) -> str:
        import rayacash

        return normalize_api_base(rayacash.api_base)

    def timeout(self) -> httpx.Timeout:
        import rayacash

        return to_timeout(rayacash.timeout)

    def max_network_retries(self) -> int:
        import rayacash

        return validate_max_network_retries(rayacash.max_network_retries)

    def user_agent(self) -> str:
        import rayacash

        info = rayacash.app_info
        return user_agent(validate_app_info(info) if info is not None else None)

    def http(self) -> HTTPClientManager:
        return _http_manager()


_lock = threading.Lock()
_manager: HTTPClientManager | None = None
_manager_clients: tuple[httpx.Client | None, httpx.AsyncClient | None] = (None, None)
_requestor: APIRequestor | None = None


def _http_manager() -> HTTPClientManager:
    global _manager, _manager_clients
    import rayacash

    clients = (rayacash.http_client, rayacash.async_http_client)
    with _lock:
        if (
            _manager is None
            or clients[0] is not _manager_clients[0]
            or clients[1] is not _manager_clients[1]
        ):
            _manager = HTTPClientManager(*clients)
            _manager_clients = clients
        return _manager


def default_requestor() -> APIRequestor:
    global _requestor
    with _lock:
        if _requestor is None:
            _requestor = APIRequestor(_GlobalConfig())
        return _requestor


def reset() -> None:
    """Olvida los clientes httpx del estilo global (los tests lo usan entre caso y caso)."""
    global _manager, _manager_clients, _requestor
    with _lock:
        _manager = None
        _manager_clients = (None, None)
        _requestor = None
