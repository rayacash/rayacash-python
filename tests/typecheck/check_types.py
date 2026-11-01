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
    assert_type(event.data.object, Union[rayacash.Transfer, rayacash.Payment, rayacash.RayaObject])


async def async_style(client: rayacash.RayaClient) -> None:
    assert_type(await client.balance.retrieve_async(), rayacash.Balance)
    assert_type(await client.payments.refund_async("id"), rayacash.Payment)
    page = await client.transfers.list_async()
    async for item in page.auto_paging_iter():
        assert_type(item, rayacash.Transfer)
    assert_type(await page.next_page_async(), rayacash.ListObject[rayacash.Transfer])


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


async def global_async_style(payment: rayacash.Payment) -> None:
    assert_type(await payment.refund_async(), rayacash.Payment)
    assert_type(await rayacash.Payment.refund_async("id"), rayacash.Payment)


def errors(error: rayacash.RayaError) -> None:
    assert_type(error.code, Optional[str])
    assert_type(error.request_id, Optional[str])
    if isinstance(error, rayacash.InvalidRequestError):
        assert_type(error.param, Optional[str])
