"""Chequeo estático de la superficie pública: lo corren mypy y pyright, nunca pytest.

Si un tipo de retorno cambia sin querer, ``assert_type`` falla en el type checker.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union
from unittest import mock

from typing_extensions import Literal, assert_type

import rayacash


def client_style(client: rayacash.RayaClient) -> None:
    assert_type(client.balance.retrieve(), rayacash.Balance)
    assert_type(client.balance.retrieve().available, float)

    transfer = client.transfers.create(
        amount=Decimal("25000.50"), destination="0000123380736153041182", idempotency_key="k"
    )
    assert_type(transfer, rayacash.Transfer)
    assert_type(transfer.counterparty, rayacash.Transfer.Counterparty)
    assert_type(transfer.counterparty.tax_id, Optional[str])
    assert_type(client.transfers.retrieve("id"), rayacash.Transfer)

    page = client.transfers.list(direction="inbound", limit=100)
    assert_type(page, rayacash.ListObject[rayacash.Transfer])
    assert_type(page.data, list[rayacash.Transfer])
    for item in page.auto_paging_iter():
        assert_type(item, rayacash.Transfer)

    payment = client.payments.create(amount=15000, metadata={"cliente_id": "8812"})
    assert_type(payment, rayacash.Payment)
    assert_type(payment.bank_transfer.alias, Optional[str])
    assert_type(payment.payer, Optional[rayacash.Payment.Payer])
    assert_type(payment.metadata, dict[str, str])
    assert_type(client.payments.retrieve("id"), rayacash.Payment)
    assert_type(client.payments.refund("id", idempotency_key="r"), rayacash.Payment)
    assert_type(client.raw_request("get", "/v1/balance"), rayacash.RayaObject)

    event = client.construct_event(b"{}", "t=1,v1=x", "whsec_x")
    assert_type(event, rayacash.Event)
    assert_type(
        event.data.object,
        Union[rayacash.Transfer, rayacash.Payment, rayacash.ConnectOrder, rayacash.RayaObject],
    )


def connected_app_style(client: rayacash.RayaClient) -> None:
    token = client.oauth.token("7650337728110670", "raya_cs_live_x", "c0d3", "https://x/cb")
    assert_type(token, rayacash.OAuthToken)
    assert_type(token.access_token, str)
    assert_type(token.user_id, str)
    assert_type(token.expires_in, Optional[int])

    user = client.users.retrieve("me")
    assert_type(user, rayacash.User)
    assert_type(user.type, rayacash.UserType)
    assert_type(user.identification, Optional[rayacash.User.Identification])
    assert_type(user.address, Optional[rayacash.User.Address])
    assert_type(user.business, Optional[rayacash.User.Business])
    assert_type(user.merchant, Optional[rayacash.User.Merchant])
    if user.business is not None:
        assert_type(user.business.representative, Optional[rayacash.User.Business.Representative])

    order = client.connect.orders.create(
        items=[{"title": "Pedido 1042", "quantity": 1, "unit_price": Decimal("45000")}],
        fee=500,
        back_urls={"success": "https://tienda.example.com/pedidos/1042"},
        auto_return="approved",
    )
    assert_type(order, rayacash.ConnectOrder)
    assert_type(order.object, Literal["connect.order", "checkout"])  # "checkout": legacy (1.1.0)
    assert_type(order.status, rayacash.ConnectOrderStatus)
    assert_type(order.fee, float)
    assert_type(order.back_urls, rayacash.ConnectOrder.BackUrls)
    assert_type(order.back_urls.success, Optional[str])
    assert_type(order.payer, Optional[rayacash.ConnectOrder.Payer])
    item: rayacash.ConnectOrder.Item = order["items"][0]  # order.items es dict.items()
    assert_type(item.unit_price, float)
    assert_type(client.connect.orders.retrieve("id"), rayacash.ConnectOrder)
    assert_type(client.connect.orders.refund("id", idempotency_key="r"), rayacash.ConnectOrder)
    assert_type(order.refund(), rayacash.ConnectOrder)


async def async_style(client: rayacash.RayaClient) -> None:
    assert_type(await client.balance.retrieve_async(), rayacash.Balance)
    assert_type(await client.payments.refund_async("id"), rayacash.Payment)
    page = await client.transfers.list_async()
    async for item in page.auto_paging_iter():
        assert_type(item, rayacash.Transfer)
    assert_type(await page.next_page_async(), rayacash.ListObject[rayacash.Transfer])
    assert_type(
        await client.oauth.token_async("id", "secret", "code", "https://x/cb"),
        rayacash.OAuthToken,
    )
    assert_type(await client.users.retrieve_async("me"), rayacash.User)
    assert_type(await client.connect.orders.create_async(items=[]), rayacash.ConnectOrder)
    assert_type(await client.connect.orders.retrieve_async("id"), rayacash.ConnectOrder)
    assert_type(await client.connect.orders.refund_async("id"), rayacash.ConnectOrder)


def global_style() -> None:
    assert_type(rayacash.Balance.retrieve(), rayacash.Balance)
    assert_type(
        rayacash.Transfer.create(amount=1, destination="alias.prueba", idempotency_key="k"),
        rayacash.Transfer,
    )
    assert_type(rayacash.Transfer.list(), rayacash.ListObject[rayacash.Transfer])
    payment = rayacash.Payment.retrieve("id")
    assert_type(payment.refund(), rayacash.Payment)
    assert_type(rayacash.Payment.refund("id"), rayacash.Payment)
    assert_type(rayacash.OAuth.token("id", "secret", "code", "https://x/cb"), rayacash.OAuthToken)
    assert_type(rayacash.User.retrieve("me"), rayacash.User)
    order = rayacash.ConnectOrder.create(items=[{"title": "x", "quantity": 1, "unit_price": 1}])
    assert_type(order, rayacash.ConnectOrder)
    assert_type(rayacash.ConnectOrder.retrieve("id"), rayacash.ConnectOrder)
    assert_type(order.refund(), rayacash.ConnectOrder)
    assert_type(rayacash.ConnectOrder.refund("id"), rayacash.ConnectOrder)


async def global_async_style(payment: rayacash.Payment, order: rayacash.ConnectOrder) -> None:
    assert_type(await payment.refund_async(), rayacash.Payment)
    assert_type(await rayacash.Payment.refund_async("id"), rayacash.Payment)
    assert_type(await order.refund_async(), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.refund_async("id"), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.create_async(items=[]), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.retrieve_async("id"), rayacash.ConnectOrder)
    assert_type(
        await rayacash.OAuth.token_async("id", "secret", "code", "https://x/cb"),
        rayacash.OAuthToken,
    )
    assert_type(await rayacash.User.retrieve_async("me"), rayacash.User)


def code_written_for_1_1_0(client: rayacash.RayaClient, event: rayacash.Event) -> None:
    """Los nombres de la 1.1.0 siguen tipando (alias deprecados hasta la 2.0.0)."""
    checkout: rayacash.Checkout = client.checkout.orders.create(items=[], fee=500)
    assert_type(checkout, rayacash.ConnectOrder)
    status: rayacash.CheckoutStatus = checkout.status
    assert_type(status, rayacash.ConnectOrderStatus)
    item: rayacash.Checkout.Item = checkout["items"][0]
    assert_type(item, rayacash.ConnectOrder.Item)
    assert_type(checkout.payer, Optional[rayacash.Checkout.Payer])
    assert_type(client.checkout.orders.retrieve(checkout_id="id"), rayacash.Checkout)
    assert_type(client.checkout.orders.refund(checkout.id, idempotency_key="r"), rayacash.Checkout)
    assert_type(
        client.connect.orders.refund(checkout_id="id", idempotency_key="r"), rayacash.Checkout
    )
    assert_type(rayacash.Checkout.create(items=[]), rayacash.ConnectOrder)
    assert_type(rayacash.Checkout.retrieve(checkout_id="id"), rayacash.ConnectOrder)
    assert_type(rayacash.Checkout.refund(checkout_id="id"), rayacash.ConnectOrder)
    assert_type(rayacash.Checkout.refund("id"), rayacash.ConnectOrder)
    assert_type(checkout.refund(), rayacash.ConnectOrder)
    if event.type == "checkout.succeeded" and isinstance(event.data.object, rayacash.Checkout):
        assert_type(event.data.object, rayacash.ConnectOrder)
    # En la 1.1.0 era un atributo común: se puede reemplazar (también con un mock) y borrar.
    client.checkout = mock.MagicMock()
    client.checkout = client.connect
    del client.checkout


async def code_written_for_1_1_0_async(client: rayacash.RayaClient) -> None:
    assert_type(await client.checkout.orders.create_async(items=[]), rayacash.Checkout)
    assert_type(
        await client.checkout.orders.retrieve_async(checkout_id="id"), rayacash.ConnectOrder
    )
    assert_type(await client.connect.orders.refund_async(checkout_id="id"), rayacash.ConnectOrder)
    assert_type(await rayacash.Checkout.retrieve_async(checkout_id="id"), rayacash.ConnectOrder)
    assert_type(await rayacash.Checkout.refund_async(checkout_id="id"), rayacash.ConnectOrder)
    assert_type(await rayacash.Checkout.create_async(items=[]), rayacash.ConnectOrder)


def errors(error: rayacash.RayaError) -> None:
    assert_type(error.code, Optional[str])
    assert_type(error.request_id, Optional[str])
    if isinstance(error, rayacash.InvalidRequestError):
        assert_type(error.param, Optional[str])
