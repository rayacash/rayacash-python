"""Listas paginadas por cursor (``{"object": "list", "data", "has_more", "next_cursor"}``)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    TypeVar,
)

from typing_extensions import Literal

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

T = TypeVar("T")


class AnyIterator(Generic[T]):
    """Sirve para ``for`` y para ``async for`` (pero no para los dos a la vez)."""

    def __init__(
        self,
        sync_factory: Callable[[], Iterator[T]],
        async_factory: Callable[[], AsyncIterator[T]],
    ) -> None:
        self._sync_factory = sync_factory
        self._async_factory = async_factory
        self._sync: Iterator[T] | None = None
        self._async: AsyncIterator[T] | None = None

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self._async is not None:
            raise TypeError("No mezcles for y async for sobre el mismo auto_paging_iter().")
        if self._sync is None:
            self._sync = self._sync_factory()
        return next(self._sync)

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        if self._sync is not None:
            raise TypeError("No mezcles for y async for sobre el mismo auto_paging_iter().")
        if self._async is None:
            self._async = self._async_factory()
        return await self._async.__anext__()


class ListObject(RayaObject, Generic[T]):
    """Una página de resultados, del más nuevo al más viejo.

    Iterarla recorre ``data`` (solo esta página). Para recorrer todas, usá
    ``auto_paging_iter()``: pide las páginas siguientes con los mismos filtros.
    """

    OBJECT_NAME: ClassVar[str | None] = "list"

    object: Literal["list"]
    data: list[T]
    has_more: bool
    next_cursor: str | None

    _retrieve_path: str | None
    _retrieve_params: dict[str, str]
    _retrieve_options: RequestOptions

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_retrieve_path", None)
        object.__setattr__(self, "_retrieve_params", {})
        object.__setattr__(self, "_retrieve_options", {})

    def _set_retrieve_context(
        self, path: str, params: dict[str, str], options: RequestOptions
    ) -> None:
        object.__setattr__(self, "_retrieve_path", path)
        object.__setattr__(self, "_retrieve_params", dict(params))
        object.__setattr__(self, "_retrieve_options", dict(options))

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    def __reversed__(self) -> Iterator[T]:  # type: ignore[override]
        return reversed(self._items())

    def __getitem__(self, key: str) -> Any:
        if not isinstance(key, str):
            raise KeyError(
                f"Una ListObject no se indexa con {key!r}: los elementos están en .data "
                f"(por ejemplo, page.data[{key!r}])."
            )
        return super().__getitem__(key)

    def _items(self) -> list[T]:
        data = self.get("data")
        return data if isinstance(data, list) else []

    def _next_params(self) -> dict[str, str] | None:
        cursor = self.get("next_cursor")
        if not self.get("has_more") or not isinstance(cursor, str) or not cursor:
            return None
        if self._retrieve_path is None:
            raise RuntimeError(
                "Esta lista no sabe cómo pedir la página siguiente (no vino de un método list): "
                "pedila vos con cursor=next_cursor."
            )
        return {**self._retrieve_params, "cursor": cursor}

    def _empty_page(self) -> ListObject[T]:
        page: ListObject[T] = ListObject.construct_from(
            {"object": "list", "data": [], "has_more": False, "next_cursor": None},
            requestor=self._requestor,
        )
        if self._retrieve_path is not None:
            page._set_retrieve_context(
                self._retrieve_path, self._retrieve_params, self._retrieve_options
            )
        return page

    def next_page(self) -> ListObject[T]:
        """La página siguiente. Si no hay más, una lista vacía (sin hacer la request)."""
        params = self._next_params()
        if params is None:
            return self._empty_page()
        assert self._retrieve_path is not None
        return self._resolve_requestor().request_list(
            self._retrieve_path, query=params, options=self._retrieve_options
        )

    async def next_page_async(self) -> ListObject[T]:
        """Como ``next_page()``, para asyncio."""
        params = self._next_params()
        if params is None:
            return self._empty_page()
        assert self._retrieve_path is not None
        return await self._resolve_requestor().request_list_async(
            self._retrieve_path, query=params, options=self._retrieve_options
        )

    def auto_paging_iter(self) -> AnyIterator[T]:
        """Todos los elementos, página por página: ``for`` o ``async for``."""
        return AnyIterator(self._auto_paging, self._auto_paging_async)

    def _auto_paging(self) -> Iterator[T]:
        page: ListObject[T] = self
        while True:
            yield from page._items()
            if page._next_params() is None:
                return
            page = page.next_page()

    async def _auto_paging_async(self) -> AsyncIterator[T]:
        page: ListObject[T] = self
        while True:
            for item in page._items():
                yield item
            if page._next_params() is None:
                return
            page = await page.next_page_async()
