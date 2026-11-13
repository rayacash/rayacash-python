"""Chequeo estático de la superficie pública: lo corren mypy y pyright, nunca pytest.

Si un tipo de retorno cambia sin querer, ``assert_type`` falla en el type checker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Union
from unittest import mock

from typing_extensions import Literal, assert_type

import rayacash
from rayacash._identity_verification_service import IdentityService, IdentityVerificationService
from rayacash._sandbox_helpers_service import SandboxHelpersService, SandboxPaymentHelpersService


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
        Union[
            rayacash.Transfer,
            rayacash.Payment,
            rayacash.ConnectOrder,
            rayacash.IdentityVerification,
            rayacash.RayaObject,
        ],
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


def connect_payouts_style(client: rayacash.RayaClient) -> None:
    # Con la clave secreta: la plata sale de tu saldo.
    payout = client.connect.payouts.create(
        amount=Decimal("60000.50"), destination="0000123305838495183140", idempotency_key="k"
    )
    assert_type(payout, rayacash.ConnectPayout)
    assert_type(payout.object, Literal["connect.payout"])
    assert_type(payout.status, rayacash.ConnectPayoutStatus)
    assert_type(payout.amount, float)
    assert_type(payout.processing_fee, float)
    assert_type(payout.net_amount, float)
    assert_type(payout.origin, rayacash.ConnectPayout.Origin)
    assert_type(payout.origin.account, str)
    assert_type(payout.origin.alias, Optional[str])
    assert_type(payout.origin.name, str)
    assert_type(payout.counterparty, rayacash.ConnectPayout.Counterparty)
    assert_type(payout.counterparty.tax_id, Optional[str])
    assert_type(payout.reference, Optional[str])
    assert_type(client.connect.payouts.retrieve("id"), rayacash.ConnectPayout)

    page = client.connect.payouts.list(status="completed", limit=100)
    assert_type(page, rayacash.ListObject[rayacash.ConnectPayout])
    assert_type(page.data, list[rayacash.ConnectPayout])
    for item in page.auto_paging_iter():
        assert_type(item, rayacash.ConnectPayout)


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
    assert_type(
        await client.connect.payouts.create_async(amount=1, destination="x", idempotency_key="k"),
        rayacash.ConnectPayout,
    )
    assert_type(await client.connect.payouts.retrieve_async("id"), rayacash.ConnectPayout)
    payouts = await client.connect.payouts.list_async(status="failed")
    assert_type(payouts, rayacash.ListObject[rayacash.ConnectPayout])
    async for payout in payouts.auto_paging_iter():
        assert_type(payout, rayacash.ConnectPayout)


def identity_style(client: rayacash.RayaClient, event: rayacash.Event) -> None:
    # Los servicios tienen nombre, aunque (como los demás) no se exportan desde rayacash.
    assert_type(client.identity, IdentityService)
    assert_type(client.identity.verifications, IdentityVerificationService)

    verification = client.identity.verifications.create(
        type="document",
        external_reference="cliente-8812",
        metadata={"plan": "pro"},
        return_url="https://tienda.example.com/cuenta",
        expires_in=86400,
        idempotency_key="k",
    )
    assert_type(verification, rayacash.IdentityVerification)
    assert_type(verification.object, Literal["identity.verification"])
    assert_type(verification.type, rayacash.IdentityVerificationType)
    assert_type(verification.status, rayacash.IdentityVerificationStatus)
    assert_type(verification.url, str)
    assert_type(verification.metadata, dict[str, str])
    assert_type(verification.reference, Optional[str])
    assert_type(verification.amount, Optional[float])
    assert_type(verification.completed_at, Optional[str])
    assert_type(verification.decline_reason, Optional[rayacash.IdentityVerification.DeclineReason])
    if verification.decline_reason is not None:
        assert_type(verification.decline_reason.code, rayacash.IdentityVerificationDeclineCode)
    checks = verification.checks
    assert_type(checks, rayacash.IdentityVerification.Checks)
    assert_type(checks.document, rayacash.IdentityVerification.DocumentCheck)
    assert_type(checks.document.status, rayacash.IdentityVerificationCheckStatus)
    assert_type(checks.liveness, rayacash.IdentityVerification.LivenessCheck)
    assert_type(checks.liveness.confidence, Optional[float])
    assert_type(checks.face_match, rayacash.IdentityVerification.FaceMatchCheck)
    assert_type(checks.face_match.similarity, Optional[float])
    assert_type(checks.registry, rayacash.IdentityVerification.RegistryCheck)
    assert_type(checks.registry.data_match, Optional[bool])
    assert_type(checks.registry.face_match, Optional[Literal["hit", "accepted", "failed"]])
    assert_type(verification.person, Optional[rayacash.IdentityVerification.Person])
    if verification.person is not None:
        assert_type(verification.person.cuil, Optional[str])
        assert_type(verification.person.address, rayacash.IdentityVerification.Address)
        assert_type(verification.person.address.city, Optional[str])
        document = verification.person.document
        assert_type(document, rayacash.IdentityVerification.IdentityDocument)
        assert_type(document.expiry_date, Optional[str])
        # El ejemplar va con document["copy"] (un valor del dict): document.copy es dict.copy().
        assert_type(document["copy"], Any)
    assert_type(verification.cancel(), rayacash.IdentityVerification)
    assert_type(verification.cancel(idempotency_key="c"), rayacash.IdentityVerification)

    biometric = client.identity.verifications.create(type="biometric", reference="idv_x")
    assert_type(biometric, rayacash.IdentityVerification)
    assert_type(client.identity.verifications.retrieve("id"), rayacash.IdentityVerification)
    assert_type(
        client.identity.verifications.cancel("id", idempotency_key="c"),
        rayacash.IdentityVerification,
    )
    page = client.identity.verifications.list(
        status="verified",
        type="document",
        external_reference="cliente-8812",
        created_gte=datetime(2026, 10, 1, tzinfo=timezone.utc),
        created_lt="2026-11-01T00:00:00-03:00",
        limit=100,
        cursor="c",
    )
    assert_type(page, rayacash.ListObject[rayacash.IdentityVerification])
    assert_type(page.data, list[rayacash.IdentityVerification])
    for item in page.auto_paging_iter():
        assert_type(item, rayacash.IdentityVerification)

    files = client.identity.verifications.files("id")
    assert_type(files, rayacash.IdentityVerificationFiles)
    assert_type(files.object, Literal["identity.verification_files"])
    assert_type(files.front, Optional[rayacash.IdentityVerificationFiles.File])
    if files.selfie is not None:
        assert_type(files.selfie.url, str)
        assert_type(files.selfie.expires_at, str)

    if event.type == "identity.verification.verified" and isinstance(
        event.data.object, rayacash.IdentityVerification
    ):
        assert_type(event.data.object.person, Optional[rayacash.IdentityVerification.Person])
        assert_type(event.data.object.cancel(), rayacash.IdentityVerification)


async def identity_async_style(
    client: rayacash.RayaClient, verification: rayacash.IdentityVerification
) -> None:
    verifications = client.identity.verifications
    assert_type(await verifications.create_async(type="document"), rayacash.IdentityVerification)
    assert_type(await verifications.retrieve_async("id"), rayacash.IdentityVerification)
    assert_type(await verifications.cancel_async("id"), rayacash.IdentityVerification)
    assert_type(await verifications.files_async("id"), rayacash.IdentityVerificationFiles)
    page = await verifications.list_async(status="declined")
    assert_type(page, rayacash.ListObject[rayacash.IdentityVerification])
    async for item in page.auto_paging_iter():
        assert_type(item, rayacash.IdentityVerification)
    assert_type(await page.next_page_async(), rayacash.ListObject[rayacash.IdentityVerification])
    assert_type(await verification.cancel_async(), rayacash.IdentityVerification)
    assert_type(await verification.cancel_async(idempotency_key="c"), rayacash.IdentityVerification)


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
    payout = rayacash.ConnectPayout.create(amount=1, destination="x", idempotency_key="k")
    assert_type(payout, rayacash.ConnectPayout)
    assert_type(rayacash.ConnectPayout.retrieve("id"), rayacash.ConnectPayout)
    assert_type(
        rayacash.ConnectPayout.list(status="pending"),
        rayacash.ListObject[rayacash.ConnectPayout],
    )


async def global_async_style(payment: rayacash.Payment, order: rayacash.ConnectOrder) -> None:
    assert_type(await payment.refund_async(), rayacash.Payment)
    assert_type(await rayacash.Payment.refund_async("id"), rayacash.Payment)
    assert_type(await order.refund_async(), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.refund_async("id"), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.create_async(items=[]), rayacash.ConnectOrder)
    assert_type(await rayacash.ConnectOrder.retrieve_async("id"), rayacash.ConnectOrder)
    assert_type(
        await rayacash.ConnectPayout.create_async(amount=1, destination="x", idempotency_key="k"),
        rayacash.ConnectPayout,
    )
    assert_type(await rayacash.ConnectPayout.retrieve_async("id"), rayacash.ConnectPayout)
    assert_type(
        await rayacash.ConnectPayout.list_async(),
        rayacash.ListObject[rayacash.ConnectPayout],
    )
    assert_type(
        await rayacash.OAuth.token_async("id", "secret", "code", "https://x/cb"),
        rayacash.OAuthToken,
    )
    assert_type(await rayacash.User.retrieve_async("me"), rayacash.User)


def identity_global_style() -> None:
    verification = rayacash.IdentityVerification.create(type="document", metadata={"plan": "pro"})
    assert_type(verification, rayacash.IdentityVerification)
    assert_type(rayacash.IdentityVerification.retrieve("id"), rayacash.IdentityVerification)
    assert_type(
        rayacash.IdentityVerification.list(status="verified", type="biometric"),
        rayacash.ListObject[rayacash.IdentityVerification],
    )
    assert_type(rayacash.IdentityVerification.cancel("id"), rayacash.IdentityVerification)
    assert_type(
        rayacash.IdentityVerification.cancel("id", idempotency_key="c"),
        rayacash.IdentityVerification,
    )
    assert_type(rayacash.IdentityVerification.files("id"), rayacash.IdentityVerificationFiles)
    assert_type(verification.cancel(), rayacash.IdentityVerification)
    assert_type(
        rayacash.IdentityVerification.construct_from({"object": "identity.verification"}),
        rayacash.IdentityVerification,
    )


async def identity_global_async_style() -> None:
    identity = rayacash.IdentityVerification
    assert_type(await identity.create_async(type="document"), rayacash.IdentityVerification)
    assert_type(await identity.retrieve_async("id"), rayacash.IdentityVerification)
    assert_type(await identity.list_async(), rayacash.ListObject[rayacash.IdentityVerification])
    assert_type(await identity.cancel_async("id"), rayacash.IdentityVerification)
    assert_type(await identity.files_async("id"), rayacash.IdentityVerificationFiles)


def sandbox_style(client: rayacash.RayaClient, event: rayacash.Event) -> None:
    # Los servicios tienen nombre, aunque (como los demás) no se exportan desde rayacash.
    assert_type(client.test_helpers, SandboxHelpersService)
    assert_type(client.test_helpers.payments, SandboxPaymentHelpersService)
    simulated = client.test_helpers.payments.simulate_transfer("id")
    assert_type(simulated, Union[rayacash.Payment, rayacash.ConnectOrder])
    assert_type(
        client.test_helpers.payments.simulate_transfer("id", amount=Decimal("1000.50")),
        Union[rayacash.Payment, rayacash.ConnectOrder],
    )
    if isinstance(simulated, rayacash.Payment):
        assert_type(simulated.failure_code, Optional[Literal["amount_mismatch"]])
    else:
        assert_type(simulated.net_amount, float)
    assert_type(
        rayacash.Payment.simulate_transfer("id", amount=1000),
        Union[rayacash.Payment, rayacash.ConnectOrder],
    )
    assert_type(event.livemode, bool)


async def sandbox_async_style(client: rayacash.RayaClient) -> None:
    assert_type(
        await client.test_helpers.payments.simulate_transfer_async("id", amount="1000.50"),
        Union[rayacash.Payment, rayacash.ConnectOrder],
    )
    assert_type(
        await rayacash.Payment.simulate_transfer_async("id"),
        Union[rayacash.Payment, rayacash.ConnectOrder],
    )


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
