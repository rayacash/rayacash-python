from __future__ import annotations

import asyncio
from typing import Any

import pytest

import rayacash
from tests import fixtures_facturador as facturador
from tests import fixtures_psp as psp
from tests.fixtures import transfer_page
from tests.fixtures_apps import PAYOUT_COMPLETED
from tests.fixtures_identity import verification_page
from tests.helpers import OTHER_KEY, TEST_KEY, MockAPI


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


def payout_page(ids: list[str], *, next_cursor: str | None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{**PAYOUT_COMPLETED, "id": payout_id} for payout_id in ids],
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


def test_connect_payouts_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, payout_page(["p1", "p2"], next_cursor="c1"))
    api.add(200, payout_page(["p3"], next_cursor=None))
    page = client.connect.payouts.list(status="completed", limit=2)
    payouts = list(page.auto_paging_iter())
    assert [payout.id for payout in payouts] == ["p1", "p2", "p3"]
    assert all(type(payout) is rayacash.ConnectPayout for payout in payouts)
    assert [dict(r.url.params) for r in api.requests] == [
        {"status": "completed", "limit": "2"},
        {"status": "completed", "limit": "2", "cursor": "c1"},
    ]
    assert {r.url.path for r in api.requests} == {"/v1/connect/payouts"}


def test_connect_payouts_async_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, payout_page(["p1"], next_cursor="c1"))
    api.add(200, payout_page(["p2"], next_cursor=None))

    async def collect() -> list[str]:
        page = await client.connect.payouts.list_async()
        return [payout.id async for payout in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["p1", "p2"]
    assert api.requests[1].url.params["cursor"] == "c1"


def queue_three_verification_pages(api: MockAPI) -> None:
    api.add(200, verification_page(["v1", "v2"], next_cursor="c1"))
    api.add(200, verification_page(["v3", "v4"], next_cursor="c2"))
    api.add(200, verification_page(["v5"], next_cursor=None))


def test_identity_verifications_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_verification_pages(api)
    page = client.identity.verifications.list(
        status="verified", limit=2, options={"api_key": OTHER_KEY}
    )
    verifications = list(page.auto_paging_iter())
    assert [verification.id for verification in verifications] == ["v1", "v2", "v3", "v4", "v5"]
    assert all(type(item) is rayacash.IdentityVerification for item in verifications)
    assert len(api.requests) == 3  # al llegar al final no pide otra página
    assert [dict(r.url.params) for r in api.requests] == [
        {"status": "verified", "limit": "2"},
        {"status": "verified", "limit": "2", "cursor": "c1"},
        {"status": "verified", "limit": "2", "cursor": "c2"},
    ]
    assert {r.url.path for r in api.requests} == {"/v1/identity/verifications"}
    # Las opciones de la primera request también viajan en las siguientes.
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {OTHER_KEY}"}


def test_identity_verifications_async_auto_paging(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    queue_three_verification_pages(api)

    async def collect() -> list[str]:
        page = await client.identity.verifications.list_async(type="document")
        return [verification.id async for verification in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["v1", "v2", "v3", "v4", "v5"]
    assert [dict(r.url.params) for r in api.requests][1:] == [
        {"type": "document", "cursor": "c1"},
        {"type": "document", "cursor": "c2"},
    ]


def test_identity_verifications_paging_can_stop_halfway(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    queue_three_verification_pages(api)
    ids: list[str] = []
    for verification in client.identity.verifications.list().auto_paging_iter():
        ids.append(verification.id)
        if len(ids) == 3:
            break
    assert ids == ["v1", "v2", "v3"]
    assert len(api.requests) == 2
    assert api.pending == 1


def test_identity_verifications_next_page_on_the_last_page(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, verification_page(["v1"], next_cursor=None))
    page = client.identity.verifications.list(status="verified")
    assert page.next_page().data == []
    assert asyncio.run(page.next_page_async()).data == []
    assert len(api.requests) == 1


def test_identity_verifications_global_auto_paging(api: MockAPI) -> None:
    rayacash.api_key = TEST_KEY
    rayacash.http_client = api.sync_client()
    queue_three_verification_pages(api)
    page = rayacash.IdentityVerification.list(limit=2)
    assert [verification.id for verification in page.auto_paging_iter()] == [
        "v1",
        "v2",
        "v3",
        "v4",
        "v5",
    ]
    assert [r.url.params.get("cursor") for r in api.requests] == [None, "c1", "c2"]
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {TEST_KEY}"}


# --- Raya PSP: psp.customers.list y psp.transfers.list ------------------------------------------


def queue_three_customer_pages(api: MockAPI) -> None:
    api.add(200, psp.customer_page(["c1", "c2"], next_cursor="k1"))
    api.add(200, psp.customer_page(["c3", "c4"], next_cursor="k2"))
    api.add(200, psp.customer_page(["c5"], next_cursor=None))


def test_psp_customers_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_customer_pages(api)
    page = client.psp.customers.list(status="active", limit=2, options={"api_key": OTHER_KEY})
    customers = list(page.auto_paging_iter())
    assert [customer.id for customer in customers] == ["c1", "c2", "c3", "c4", "c5"]
    assert all(type(customer) is rayacash.PspCustomer for customer in customers)
    assert len(api.requests) == 3  # al llegar al final no pide otra página
    assert [dict(r.url.params) for r in api.requests] == [
        {"status": "active", "limit": "2"},
        {"status": "active", "limit": "2", "cursor": "k1"},
        {"status": "active", "limit": "2", "cursor": "k2"},
    ]
    assert {r.url.path for r in api.requests} == {"/v1/psp/customers"}
    # Las opciones de la primera request también viajan en las siguientes.
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {OTHER_KEY}"}


def test_psp_customers_async_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_customer_pages(api)

    async def collect() -> list[str]:
        page = await client.psp.customers.list_async(external_reference="cliente-8812")
        return [customer.id async for customer in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["c1", "c2", "c3", "c4", "c5"]
    assert [dict(r.url.params) for r in api.requests][1:] == [
        {"external_reference": "cliente-8812", "cursor": "k1"},
        {"external_reference": "cliente-8812", "cursor": "k2"},
    ]


def test_psp_customers_paging_can_stop_halfway(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_customer_pages(api)
    ids: list[str] = []
    for customer in client.psp.customers.list().auto_paging_iter():
        ids.append(customer.id)
        if len(ids) == 3:
            break
    assert ids == ["c1", "c2", "c3"]
    assert len(api.requests) == 2
    assert api.pending == 1


def test_psp_transfers_auto_paging_keeps_the_customer_filter(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, psp.transfer_page(["t1", "t2"], next_cursor="k1"))
    api.add(200, psp.transfer_page(["t3"], next_cursor=None))
    page = client.psp.transfers.list(customer=psp.CUSTOMER_ID, direction="inbound", limit=2)
    transfers = list(page.auto_paging_iter())
    assert [transfer.id for transfer in transfers] == ["t1", "t2", "t3"]
    assert all(type(transfer) is rayacash.PspTransfer for transfer in transfers)
    assert [dict(r.url.params) for r in api.requests] == [
        {"customer": psp.CUSTOMER_ID, "direction": "inbound", "limit": "2"},
        {"customer": psp.CUSTOMER_ID, "direction": "inbound", "limit": "2", "cursor": "k1"},
    ]
    assert {r.url.path for r in api.requests} == {"/v1/psp/transfers"}


def test_psp_transfers_async_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, psp.transfer_page(["t1"], next_cursor="k1"))
    api.add(200, psp.transfer_page(["t2"], next_cursor=None))

    async def collect() -> list[str]:
        page = await client.psp.transfers.list_async(status="completed")
        return [transfer.id async for transfer in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["t1", "t2"]
    assert api.requests[1].url.params["cursor"] == "k1"


def test_psp_next_page_on_the_last_page(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, psp.transfer_page(["t1"], next_cursor=None))
    page = client.psp.transfers.list(customer=psp.CUSTOMER_ID)
    assert page.next_page().data == []
    assert asyncio.run(page.next_page_async()).data == []
    assert len(api.requests) == 1


def test_psp_global_auto_paging(api: MockAPI) -> None:
    rayacash.api_key = TEST_KEY
    rayacash.http_client = api.sync_client()
    queue_three_customer_pages(api)
    page = rayacash.PspCustomer.list(limit=2)
    assert [customer.id for customer in page.auto_paging_iter()] == ["c1", "c2", "c3", "c4", "c5"]
    assert [r.url.params.get("cursor") for r in api.requests] == [None, "k1", "k2"]
    api.add(200, psp.transfer_page(["t1"], next_cursor="k1"))
    api.add(200, psp.transfer_page(["t2"], next_cursor=None))
    transfers = rayacash.PspTransfer.list(customer=psp.CUSTOMER_ID)
    assert [transfer.id for transfer in transfers.auto_paging_iter()] == ["t1", "t2"]
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {TEST_KEY}"}


# --- Facturador: invoices.list -------------------------------------------------------------------


def queue_three_invoice_pages(api: MockAPI) -> None:
    api.add(200, facturador.invoice_page(["i1", "i2"], next_cursor="k1"))
    api.add(200, facturador.invoice_page(["i3", "i4"], next_cursor="k2"))
    api.add(200, facturador.invoice_page(["i5"], next_cursor=None))


def test_invoices_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_invoice_pages(api)
    page = client.invoices.list(
        status="issued",
        created_gte="2026-11-01T00:00:00-03:00",
        limit=2,
        options={"api_key": OTHER_KEY},
    )
    invoices = list(page.auto_paging_iter())
    assert [invoice.id for invoice in invoices] == ["i1", "i2", "i3", "i4", "i5"]
    assert all(type(invoice) is rayacash.Invoice for invoice in invoices)
    assert len(api.requests) == 3  # al llegar al final no pide otra página
    filters = {"status": "issued", "created_gte": "2026-11-01T00:00:00-03:00", "limit": "2"}
    assert [dict(r.url.params) for r in api.requests] == [
        filters,
        {**filters, "cursor": "k1"},
        {**filters, "cursor": "k2"},
    ]
    assert {r.url.path for r in api.requests} == {"/v1/invoices"}
    # Las opciones de la primera request también viajan en las siguientes.
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {OTHER_KEY}"}


def test_invoices_async_auto_paging(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_invoice_pages(api)

    async def collect() -> list[str]:
        page = await client.invoices.list_async(status="failed")
        return [invoice.id async for invoice in page.auto_paging_iter()]

    assert asyncio.run(collect()) == ["i1", "i2", "i3", "i4", "i5"]
    assert [dict(r.url.params) for r in api.requests][1:] == [
        {"status": "failed", "cursor": "k1"},
        {"status": "failed", "cursor": "k2"},
    ]


def test_invoices_paging_can_stop_halfway(client: rayacash.RayaClient, api: MockAPI) -> None:
    queue_three_invoice_pages(api)
    ids: list[str] = []
    for invoice in client.invoices.list().auto_paging_iter():
        ids.append(invoice.id)
        if len(ids) == 3:
            break
    assert ids == ["i1", "i2", "i3"]
    assert len(api.requests) == 2
    assert api.pending == 1


def test_invoices_next_page_on_the_last_page(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, facturador.invoice_page(["i1"], next_cursor=None))
    page = client.invoices.list(status="pending")
    assert page.next_page().data == []
    assert asyncio.run(page.next_page_async()).data == []
    assert len(api.requests) == 1


def test_invoices_global_auto_paging(api: MockAPI) -> None:
    rayacash.api_key = TEST_KEY
    rayacash.http_client = api.sync_client()
    queue_three_invoice_pages(api)
    page = rayacash.Invoice.list(limit=2)
    assert [invoice.id for invoice in page.auto_paging_iter()] == ["i1", "i2", "i3", "i4", "i5"]
    assert [r.url.params.get("cursor") for r in api.requests] == [None, "k1", "k2"]
    assert {r.headers["authorization"] for r in api.requests} == {f"Bearer {TEST_KEY}"}
