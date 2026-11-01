from __future__ import annotations

import asyncio

import pytest

import rayacash
from tests.fixtures import transfer_page
from tests.helpers import OTHER_KEY, MockAPI


def queue_three_pages(api: MockAPI) -> None:
    api.add(200, transfer_page(["t1", "t2"], next_cursor="c1"))
    api.add(200, transfer_page(["t3", "t4"], next_cursor="c2"))
    api.add(200, transfer_page(["t5"], next_cursor=None))


def test_auto_paging_iter_walks_every_page(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_pages(api)
    page = client.transfers.list(direction="inbound", limit=2, options={"api_key": OTHER_KEY})
    ids = [transfer.id for transfer in page.auto_paging_iter()]
    assert ids == ["t1", "t2", "t3", "t4", "t5"]
    assert len(api.requests) == 3  # al llegar al final no pide otra página
    assert [dict(r.url.params) for r in api.requests] == [
        {"direction": "inbound", "limit": "2"},
        {"direction": "inbound", "limit": "2", "cursor": "c1"},
        {"direction": "inbound", "limit": "2", "cursor": "c2"},
    ]
    # Las opciones de la primera request también viajan en las siguientes.
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {OTHER_KEY}"}


def test_async_for(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_pages(api)

    async def collect() -> list[str]:
        page = await client.transfers.list_async(direction="inbound")
        return [transfer.id async for transfer in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["t1", "t2", "t3", "t4", "t5"]
    assert api.requests[2].url.params["cursor"] == "c2"


def test_async_for_over_a_sync_page(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_pages(api)
    page = client.transfers.list()

    async def collect() -> list[str]:
        return [transfer.id async for transfer in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["t1", "t2", "t3", "t4", "t5"]


def test_mixing_for_and_async_for_fails(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, transfer_page(["t1", "t2"], next_cursor=None))
    iterator = client.transfers.list().auto_paging_iter()
    assert next(iterator).id == "t1"

    async def mix() -> None:
        await iterator.__anext__()

    with pytest.raises(TypeError, match="No mezcles"):
        asyncio.run(mix())


def test_mixing_async_then_sync_fails(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, transfer_page(["t1", "t2"], next_cursor=None))
    iterator = client.transfers.list().auto_paging_iter()

    async def first() -> str:
        transfer = await iterator.__anext__()
        return transfer.id

    assert asyncio.run(first()) == "t1"
    with pytest.raises(TypeError, match="No mezcles"):
        next(iterator)


def test_next_page_on_the_last_page_makes_no_request(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, transfer_page(["t1"], next_cursor=None))
    page = client.transfers.list(direction="outbound")
    empty = page.next_page()
    assert list(empty) == []
    assert empty.has_more is False
    assert asyncio.run(page.next_page_async()).data == []
    assert len(api.requests) == 1
    assert list(empty.auto_paging_iter()) == []


def test_has_more_without_a_cursor_stops(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, {"object": "list", "data": [], "has_more": True, "next_cursor": None})
    assert list(client.transfers.list().auto_paging_iter()) == []
    assert len(api.requests) == 1


def test_a_list_without_context_cannot_fetch_more() -> None:
    page: rayacash.ListObject[rayacash.Transfer] = rayacash.ListObject.construct_from(
        transfer_page(["t1"], next_cursor="c1")
    )
    with pytest.raises(RuntimeError, match="cursor=next_cursor"):
        page.next_page()
    assert [t.id for t in page] == ["t1"]
