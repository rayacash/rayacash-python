"""Chequeo estático de la superficie pública: lo corren mypy y pyright, nunca pytest.

Si un tipo de retorno cambia sin querer, ``assert_type`` falla en el type checker.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union

from typing_extensions import assert_type

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
        Union[rayacash.Transfer, rayacash.Payment, rayacash.Checkout, rayacash.RayaObject],
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

    checkout = client.checkout.orders.create(
        items=[{"title": "Pedido 1042", "quantity": 1, "unit_price": Decimal("45000")}],
        fee=500,
        back_urls={"success": "https://tienda.example.com/pedidos/1042"},
        auto_return="approved",
    )
    assert_type(checkout, rayacash.Checkout)
    assert_type(checkout.status, rayacash.CheckoutStatus)
    assert_type(checkout.fee, float)
    assert_type(checkout.back_urls, rayacash.Checkout.BackUrls)
    assert_type(checkout.back_urls.success, Optional[str])
    assert_type(checkout.payer, Optional[rayacash.Checkout.Payer])
    item: rayacash.Checkout.Item = checkout["items"][0]  # checkout.items es dict.items()
    assert_type(item.unit_price, float)
    assert_type(client.checkout.orders.retrieve("id"), rayacash.Checkout)
    assert_type(client.checkout.orders.refund("id", idempotency_key="r"), rayacash.Checkout)
    assert_type(checkout.refund(), rayacash.Checkout)


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
    assert_type(await client.checkout.orders.create_async(items=[]), rayacash.Checkout)
    assert_type(await client.checkout.orders.refund_async("id"), rayacash.Checkout)


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
    checkout = rayacash.Checkout.create(items=[{"title": "x", "quantity": 1, "unit_price": 1}])
    assert_type(checkout, rayacash.Checkout)
    assert_type(rayacash.Checkout.retrieve("id"), rayacash.Checkout)
    assert_type(checkout.refund(), rayacash.Checkout)
    assert_type(rayacash.Checkout.refund("id"), rayacash.Checkout)


async def global_async_style(payment: rayacash.Payment, checkout: rayacash.Checkout) -> None:
    assert_type(await payment.refund_async(), rayacash.Payment)
    assert_type(await rayacash.Payment.refund_async("id"), rayacash.Payment)
    assert_type(await checkout.refund_async(), rayacash.Checkout)
    assert_type(await rayacash.Checkout.refund_async("id"), rayacash.Checkout)
    assert_type(
        await rayacash.OAuth.token_async("id", "secret", "code", "https://x/cb"),
        rayacash.OAuthToken,
    )
    assert_type(await rayacash.User.retrieve_async("me"), rayacash.User)


def errors(error: rayacash.RayaError) -> None:
    assert_type(error.code, Optional[str])
    assert_type(error.request_id, Optional[str])
    if isinstance(error, rayacash.InvalidRequestError):
        assert_type(error.param, Optional[str])
