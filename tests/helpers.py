"""Un servidor falso para los tests: nada sale a la red."""

from __future__ import annotations

import asyncio
import copy
import json
from collections import deque
from typing import Any

import httpx

import rayacash

TEST_KEY = "raya_sk_live_" + "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"
OTHER_KEY = "raya_sk_live_" + "ZYXWVUTSRQPONMLKJIHGFEDCBAzyxwvutsrqponmlkjihgfe"


class MockAPI:
    """Devuelve las respuestas encoladas, en orden, y guarda cada request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._queue: deque[httpx.Response | Exception] = deque()
        self._count = 0

    def add(
        self,
        status: int = 200,
        json_body: Any = None,
        *,
        headers: dict[str, str] | None = None,
        text: str | None = None,
    ) -> None:
        self._count += 1
        all_headers = {"Raya-Request-Id": f"req_test{self._count:020d}", **(headers or {})}
        if text is not None:
            response = httpx.Response(status, text=text, headers=all_headers)
        else:
            response = httpx.Response(status, json=copy.deepcopy(json_body), headers=all_headers)
        self._queue.append(response)

    def add_error(
        self,
        status: int,
        code: str,
        message: str = "Mensaje de prueba.",
        data: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.add(
            status, {"error": {"code": code, "message": message, "data": data}}, headers=headers
        )

    def fail_with(self, exc: Exception) -> None:
        self._queue.append(exc)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._queue:
            raise AssertionError(f"Request inesperada: {request.method} {request.url}")
        item = self._queue.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self) -> Any:
        return json.loads(self.last.content)

    @property
    def pending(self) -> int:
        return len(self._queue)

    def sync_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def client(self, api_key: str | None = TEST_KEY, **kwargs: Any) -> rayacash.RayaClient:
        return rayacash.RayaClient(
            api_key,
            http_client=self.sync_client(),
            async_http_client=self.async_client(),
            **kwargs,
        )


class Caller:
    """Llama a un método en su versión sync o en la ``*_async`` (con su propio event loop)."""

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def __call__(self, owner: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        if self.mode == "sync":
            return getattr(owner, name)(*args, **kwargs)
        return asyncio.run(getattr(owner, name + "_async")(*args, **kwargs))

    def __repr__(self) -> str:
        return self.mode
