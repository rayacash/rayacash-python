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
from rayacash._psp_service import (
    PspBalanceService,
    PspCustomerService,
    PspService,
    PspTransferService,
)
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
            rayacash.PspCustomer,
            rayacash.PspTransfer,
            rayacash.PspDocumentRequest,
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


def psp_style(client: rayacash.RayaClient, event: rayacash.Event) -> None:
    # Los servicios tienen nombre, aunque (como los demás) no se exportan desde rayacash.
    assert_type(client.psp, PspService)
    assert_type(client.psp.customers, PspCustomerService)
    assert_type(client.psp.transfers, PspTransferService)
    assert_type(client.psp.balance, PspBalanceService)

    # Las tres formas de create, una por @overload: con Identidad alcanza la verificación.
    customer = client.psp.customers.create(
        identity_verification="idv_3kT9vQ2mXw7Lp0aBcD4eF6gH",
        external_reference="cliente-8812",
        metadata={"plan": "pro"},
        idempotency_key="k",
    )
    assert_type(customer, rayacash.PspCustomer)
    assert_type(customer.object, Literal["psp.customer"])
    assert_type(customer.status, rayacash.PspCustomerStatus)
    assert_type(customer.person_type, rayacash.PspCustomerPersonType)
    assert_type(customer.tax_id, str)
    assert_type(customer.balance, float)
    assert_type(customer.cvu, Optional[rayacash.PspCustomer.Cvu])
    if customer.cvu is not None:
        assert_type(customer.cvu.account, str)
        assert_type(customer.cvu.alias, Optional[str])
        assert_type(customer.cvu.status, rayacash.PspCvuStatus)
        assert_type(customer.cvu.closed_at, Optional[str])
    assert_type(customer.blocked_by, Optional[rayacash.PspCustomerBlockedBy])
    assert_type(customer.identity_verification, Optional[str])
    assert_type(customer.decline_reason, Optional[rayacash.PspCustomer.DeclineReason])
    if customer.decline_reason is not None:
        assert_type(customer.decline_reason.code, rayacash.PspCustomerDeclineCode)
    assert_type(customer.metadata, dict[str, str])
    assert_type(customer.block(), rayacash.PspCustomer)
    assert_type(customer.unblock(idempotency_key="u"), rayacash.PspCustomer)
    assert_type(customer.close(), rayacash.PspCustomer)
    assert_type(customer.recreate(options={"timeout": 90}), rayacash.PspCustomer)

    with_photos = client.psp.customers.create(
        tax_id="27123456781",
        name="María Laura Ejemplo",
        person_type="F",
        document_front_url="https://x/frente.jpg",
        document_back_url="https://x/dorso.jpg",
        selfie_url="https://x/selfie.jpg",
        external_reference="cliente-8812",
    )
    assert_type(with_photos, rayacash.PspCustomer)
    company = client.psp.customers.create(
        tax_id="30712345672",
        name="Distribuidora Ejemplo S. A.",
        person_type="J",
        metadata={"plan": "pro"},
        idempotency_key="k",
    )
    assert_type(company, rayacash.PspCustomer)
    assert_type(client.psp.customers.retrieve("id"), rayacash.PspCustomer)
    page = client.psp.customers.list(
        status="blocked",
        external_reference="cliente-8812",
        created_gte=datetime(2026, 10, 1, tzinfo=timezone.utc),
        created_lt="2026-11-01T00:00:00-03:00",
        limit=100,
        cursor="c",
    )
    assert_type(page, rayacash.ListObject[rayacash.PspCustomer])
    for item in page.auto_paging_iter():
        assert_type(item, rayacash.PspCustomer)

    balance = client.psp.customers.retrieve_balance("id")
    assert_type(balance, rayacash.PspCustomerBalance)
    assert_type(balance.object, Literal["psp.customer_balance"])
    assert_type(balance.customer, str)
    assert_type(balance.available, float)
    assert_type(balance.transferable, float)
    assert_type(client.psp.customers.block("id"), rayacash.PspCustomer)
    assert_type(client.psp.customers.unblock("id", idempotency_key="u"), rayacash.PspCustomer)
    assert_type(client.psp.customers.close("id"), rayacash.PspCustomer)
    assert_type(client.psp.customers.recreate("id"), rayacash.PspCustomer)

    transfer = client.psp.transfers.create(
        customer="pspc_x",
        amount=Decimal("18350.50"),
        destination="alias.ejemplo",
        idempotency_key="k",
    )
    assert_type(transfer, rayacash.PspTransfer)
    assert_type(transfer.object, Literal["psp.transfer"])
    assert_type(transfer.direction, rayacash.PspTransferDirection)
    assert_type(transfer.status, rayacash.PspTransferStatus)
    assert_type(transfer.fee, float)
    assert_type(transfer.account, str)
    assert_type(transfer.counterparty, rayacash.PspTransfer.Counterparty)
    assert_type(transfer.counterparty.tax_id, Optional[str])
    assert_type(transfer.reference, Optional[str])
    assert_type(client.psp.transfers.retrieve("id"), rayacash.PspTransfer)
    transfers = client.psp.transfers.list(
        customer="pspc_x", direction="outbound", status="failed", limit=10
    )
    assert_type(transfers, rayacash.ListObject[rayacash.PspTransfer])
    assert_type(transfers.data, list[rayacash.PspTransfer])

    totals = client.psp.balance.retrieve()
    assert_type(totals, rayacash.PspBalance)
    assert_type(totals.object, Literal["psp.balance"])
    assert_type(totals.customers_balance, float)

    if event.type == "psp.document_request.created" and isinstance(
        event.data.object, rayacash.PspDocumentRequest
    ):
        request = event.data.object
        assert_type(request.status, rayacash.PspDocumentRequestStatus)
        assert_type(request.submitted_at, Optional[str])
    if event.type == "psp.customer.activated" and isinstance(
        event.data.object, rayacash.PspCustomer
    ):
        assert_type(event.data.object.block(), rayacash.PspCustomer)


async def psp_async_style(client: rayacash.RayaClient, customer: rayacash.PspCustomer) -> None:
    customers = client.psp.customers
    assert_type(await customers.create_async(identity_verification="idv_x"), rayacash.PspCustomer)
    assert_type(
        await customers.create_async(
            tax_id="x",
            name="y",
            person_type="F",
            document_front_url="https://x/frente.jpg",
            document_back_url="https://x/dorso.jpg",
            selfie_url="https://x/selfie.jpg",
        ),
        rayacash.PspCustomer,
    )
    assert_type(
        await customers.create_async(tax_id="x", name="y", person_type="J"), rayacash.PspCustomer
    )
    assert_type(await customers.retrieve_async("id"), rayacash.PspCustomer)
    page = await customers.list_async(status="active")
    assert_type(page, rayacash.ListObject[rayacash.PspCustomer])
    async for item in page.auto_paging_iter():
        assert_type(item, rayacash.PspCustomer)
    assert_type(await customers.retrieve_balance_async("id"), rayacash.PspCustomerBalance)
    assert_type(await customers.block_async("id"), rayacash.PspCustomer)
    assert_type(await customers.unblock_async("id"), rayacash.PspCustomer)
    assert_type(await customers.close_async("id"), rayacash.PspCustomer)
    assert_type(await customers.recreate_async("id", idempotency_key="r"), rayacash.PspCustomer)
    assert_type(await customer.block_async(), rayacash.PspCustomer)
    assert_type(await customer.unblock_async(), rayacash.PspCustomer)
    assert_type(await customer.close_async(idempotency_key="c"), rayacash.PspCustomer)
    assert_type(await customer.recreate_async(), rayacash.PspCustomer)
    transfers = client.psp.transfers
    assert_type(
        await transfers.create_async(customer="c", amount=1, destination="x", idempotency_key="k"),
        rayacash.PspTransfer,
    )
    assert_type(await transfers.retrieve_async("id"), rayacash.PspTransfer)
    assert_type(
        await transfers.list_async(direction="inbound"), rayacash.ListObject[rayacash.PspTransfer]
    )
    assert_type(await client.psp.balance.retrieve_async(), rayacash.PspBalance)


def psp_global_style() -> None:
    customer = rayacash.PspCustomer.create(tax_id="x", name="y", person_type="J")
    assert_type(customer, rayacash.PspCustomer)
    assert_type(
        rayacash.PspCustomer.create(identity_verification="idv_x", metadata={"plan": "pro"}),
        rayacash.PspCustomer,
    )
    assert_type(
        rayacash.PspCustomer.create(
            tax_id="x",
            name="y",
            person_type="F",
            document_front_url="https://x/frente.jpg",
            document_back_url="https://x/dorso.jpg",
            selfie_url="https://x/selfie.jpg",
            idempotency_key="k",
        ),
        rayacash.PspCustomer,
    )
    assert_type(rayacash.PspCustomer.retrieve("id"), rayacash.PspCustomer)
    assert_type(
        rayacash.PspCustomer.list(status="closed"), rayacash.ListObject[rayacash.PspCustomer]
    )
    assert_type(rayacash.PspCustomer.retrieve_balance("id"), rayacash.PspCustomerBalance)
    assert_type(rayacash.PspCustomer.block("id"), rayacash.PspCustomer)
    assert_type(rayacash.PspCustomer.unblock("id", idempotency_key="u"), rayacash.PspCustomer)
    assert_type(rayacash.PspCustomer.close("id"), rayacash.PspCustomer)
    assert_type(rayacash.PspCustomer.recreate("id"), rayacash.PspCustomer)
    assert_type(customer.block(), rayacash.PspCustomer)
    assert_type(
        rayacash.PspTransfer.create(customer="c", amount=1, destination="x", idempotency_key="k"),
        rayacash.PspTransfer,
    )
    assert_type(rayacash.PspTransfer.retrieve("id"), rayacash.PspTransfer)
    assert_type(rayacash.PspTransfer.list(customer="c"), rayacash.ListObject[rayacash.PspTransfer])
    assert_type(rayacash.PspBalance.retrieve(), rayacash.PspBalance)
    assert_type(
        rayacash.PspCustomer.construct_from({"object": "psp.customer"}), rayacash.PspCustomer
    )


async def psp_global_async_style() -> None:
    customer = rayacash.PspCustomer
    assert_type(await customer.create_async(identity_verification="idv_x"), rayacash.PspCustomer)
    assert_type(
        await customer.create_async(
            tax_id="x",
            name="y",
            person_type="F",
            document_front_url="https://x/frente.jpg",
            document_back_url="https://x/dorso.jpg",
            selfie_url="https://x/selfie.jpg",
        ),
        rayacash.PspCustomer,
    )
    assert_type(
        await customer.create_async(tax_id="x", name="y", person_type="J", external_reference="r"),
        rayacash.PspCustomer,
    )
    assert_type(await customer.retrieve_async("id"), rayacash.PspCustomer)
    assert_type(await customer.list_async(), rayacash.ListObject[rayacash.PspCustomer])
    assert_type(await customer.retrieve_balance_async("id"), rayacash.PspCustomerBalance)
    assert_type(await customer.block_async("id"), rayacash.PspCustomer)
    assert_type(await customer.unblock_async("id"), rayacash.PspCustomer)
    assert_type(await customer.close_async("id"), rayacash.PspCustomer)
    assert_type(await customer.recreate_async("id"), rayacash.PspCustomer)
    assert_type(
        await rayacash.PspTransfer.create_async(
            customer="c", amount=1, destination="x", idempotency_key="k"
        ),
        rayacash.PspTransfer,
    )
    assert_type(await rayacash.PspTransfer.retrieve_async("id"), rayacash.PspTransfer)
    assert_type(await rayacash.PspTransfer.list_async(), rayacash.ListObject[rayacash.PspTransfer])
    assert_type(await rayacash.PspBalance.retrieve_async(), rayacash.PspBalance)


async def psp_create_forms_that_do_not_type(client: rayacash.RayaClient) -> None:
    # Lo que la API rechaza no tipa: identity_verification con datos o fotos, una persona humana
    # sin las fotos, una jurídica con fotos, gender (ya no existe) o un id que no es un str. mypy
    # exige que cada ignore haga falta (warn_unused_ignores, de --strict).
    customers = client.psp.customers
    customers.create(identity_verification="idv_x", tax_id="27123456781")  # type: ignore[call-overload]
    customers.create(identity_verification="idv_x", selfie_url="https://x/s.jpg")  # type: ignore[call-overload]
    customers.create(tax_id="27123456781", name="María", person_type="F")  # type: ignore[call-overload]
    customers.create(tax_id="x", name="y", person_type="J", selfie_url="https://x")  # type: ignore[call-overload]
    customers.create(tax_id="x", name="y", person_type="J", gender="F")  # type: ignore[call-overload]
    customers.create(identity_verification=1234)  # type: ignore[call-overload]
    customers.create()  # type: ignore[call-overload]
    await customers.create_async(identity_verification="idv_x", name="y")  # type: ignore[call-overload]
    rayacash.PspCustomer.create(identity_verification="idv_x", person_type="F")  # type: ignore[call-overload]
    await rayacash.PspCustomer.create_async(tax_id="x", name="y")  # type: ignore[call-overload]


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
