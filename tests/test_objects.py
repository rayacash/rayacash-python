from __future__ import annotations

import copy
import json
import pickle
from typing import Any

import pytest

import rayacash
from rayacash._object_classes import OBJECT_CLASSES
from rayacash._raya_object import convert_to_raya_object
from tests import fixtures_psp as psp
from tests.fixtures import (
    EVENT_PAYMENT_SUCCEEDED,
    PAYMENT_PENDING,
    PAYMENT_SUCCEEDED,
    TRANSFER_INBOUND,
    TRANSFER_LIST,
)
from tests.fixtures_apps import (
    ACCESS_TOKEN,
    EVENT_ORDER_SUCCEEDED,
    NOTIFICATION_URL,
    OAUTH_TOKEN,
    ORDER_ID,
    ORDER_PENDING,
    ORDER_SUCCEEDED,
    PAYOUT_COMPLETED,
    PAYOUT_DESTINATION,
    PAYOUT_ID,
    PAYOUT_LIST,
    PAYOUT_ORIGIN_ACCOUNT,
    PAYOUT_PENDING,
    SANDBOX_ACCESS_TOKEN,
    USER,
    USER_BUSINESS,
    USER_ID,
)
from tests.fixtures_identity import (
    EVENT_VERIFICATION_VERIFIED,
    PERSON,
    VERIFICATION_BIOMETRIC_VERIFIED,
    VERIFICATION_DECLINED,
    VERIFICATION_FILES,
    VERIFICATION_ID,
    VERIFICATION_LIST,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
)
from tests.fixtures_sandbox import EVENT_SANDBOX_PAYMENT_SUCCEEDED


def test_transfer_is_a_typed_dict_with_attribute_access() -> None:
    transfer: Any = convert_to_raya_object(TRANSFER_INBOUND)
    assert type(transfer) is rayacash.Transfer
    assert isinstance(transfer, dict)
    transfer = convert_to_raya_object(TRANSFER_INBOUND)  # Any otra vez: el isinstance lo achica
    assert transfer.id == transfer["id"] == TRANSFER_INBOUND["id"]
    assert transfer.fee == 130.41
    assert type(transfer.counterparty) is rayacash.Transfer.Counterparty
    assert transfer.counterparty.alias is None
    assert transfer.counterparty.account == "0000123319112992888845"


def test_values_stay_as_raw_json() -> None:
    transfer = convert_to_raya_object(TRANSFER_INBOUND)
    assert json.loads(json.dumps(transfer)) == TRANSFER_INBOUND
    assert transfer.to_dict() == TRANSFER_INBOUND
    assert type(transfer.to_dict()["counterparty"]) is dict
    assert isinstance(transfer.amount, int)
    assert isinstance(transfer.net_amount, float)
    assert isinstance(transfer.created_at, str)


def test_payment_nested_objects_and_plain_metadata() -> None:
    pending = convert_to_raya_object(PAYMENT_PENDING)
    assert type(pending) is rayacash.Payment
    assert type(pending.bank_transfer) is rayacash.Payment.BankTransfer
    assert pending.payer is None
    assert type(pending.metadata) is dict  # dict común: las claves son tuyas
    succeeded = convert_to_raya_object(PAYMENT_SUCCEEDED)
    assert type(succeeded.payer) is rayacash.Payment.Payer
    assert succeeded.payer.name == "María Ejemplo"


def test_metadata_keys_can_shadow_dict_methods() -> None:
    payment = convert_to_raya_object({**PAYMENT_PENDING, "metadata": {"items": "3", "keys": "x"}})
    assert payment.metadata["items"] == "3"


def test_unknown_fields_and_objects_are_kept() -> None:
    data = {**TRANSFER_INBOUND, "nuevo_campo": {"a": 1}, "otro": [{"object": "algo_nuevo", "x": 2}]}
    transfer: Any = convert_to_raya_object(data)
    assert transfer.nuevo_campo == {"a": 1}
    assert type(transfer.nuevo_campo) is rayacash.RayaObject
    assert type(transfer.otro[0]) is rayacash.RayaObject
    assert transfer.otro[0]["x"] == 2
    assert type(convert_to_raya_object({"object": "nuevo"})) is rayacash.RayaObject
    assert convert_to_raya_object([1, "x", None]) == [1, "x", None]


def test_missing_fields_raise_attribute_error() -> None:
    balance = convert_to_raya_object({"object": "balance", "available": 1, "currency": "ARS"})
    with pytest.raises(AttributeError, match="no tiene el campo 'inexistente'"):
        balance.inexistente
    with pytest.raises(AttributeError):
        balance._privado
    with pytest.raises(KeyError):
        balance["inexistente"]
    assert getattr(balance, "inexistente", "default") == "default"


def test_setting_and_deleting_fields() -> None:
    obj: Any = rayacash.RayaObject()
    obj.nombre = "x"
    assert obj == {"nombre": "x"}
    del obj.nombre
    assert obj == {}
    with pytest.raises(AttributeError):
        del obj.nombre
    obj._interno = 1  # los atributos con _ no son datos
    assert obj == {}
    assert obj._interno == 1
    del obj._interno


def test_str_and_repr() -> None:
    payment = convert_to_raya_object(PAYMENT_PENDING)
    assert json.loads(str(payment)) == PAYMENT_PENDING
    assert repr(payment).startswith(f"<Payment payment id={PAYMENT_PENDING['id']} at 0x")
    assert "JSON: {" in repr(payment)
    assert repr(rayacash.RayaObject()).startswith("<RayaObject at 0x")


def test_pickle_copy_and_deepcopy() -> None:
    payment = convert_to_raya_object(PAYMENT_SUCCEEDED)
    restored = pickle.loads(pickle.dumps(payment))
    assert type(restored) is rayacash.Payment
    assert type(restored.payer) is rayacash.Payment.Payer
    assert restored == payment
    assert restored._requestor is None

    shallow = copy.copy(payment)
    assert type(shallow) is rayacash.Payment
    assert shallow == payment

    deep = copy.deepcopy(payment)
    deep.metadata["cliente_id"] = "otro"
    assert payment.metadata["cliente_id"] == "8812"


def test_event_hydrates_its_object() -> None:
    event = rayacash.Event.construct_from(EVENT_PAYMENT_SUCCEEDED)
    assert type(event.data) is rayacash.Event.Data
    assert type(event.data.object) is rayacash.Payment
    assert event.data.object.status == "succeeded"
    test_event = rayacash.Event.construct_from(
        {
            "id": "evt_x",
            "object": "event",
            "type": "webhook.test",
            "data": {"object": {"object": "test"}},
        }
    )
    assert type(test_event.data.object) is rayacash.RayaObject


def test_event_livemode_is_false_in_a_sandbox() -> None:
    event = rayacash.Event.construct_from(EVENT_SANDBOX_PAYMENT_SUCCEEDED)
    assert event.livemode is False
    assert event["livemode"] is False
    # En el orden del sobre: entre created_at y data.
    assert list(event) == ["id", "object", "type", "api_version", "created_at", "livemode", "data"]
    payment = event.data.object
    assert type(payment) is rayacash.Payment
    assert payment.payer is not None
    assert payment.payer.name == "Pagador de prueba"
    assert event.to_dict() == EVENT_SANDBOX_PAYMENT_SUCCEEDED


def test_an_event_without_livemode_stays_as_it_came() -> None:
    # Un evento creado antes de que la API sumara livemode (un reintento o un reenvío desde el
    # dashboard) no lo trae: el SDK no lo inventa, y get() lo lee como de la cuenta real (antes no
    # había sandboxes).
    event = rayacash.Event.construct_from(EVENT_PAYMENT_SUCCEEDED)
    assert "livemode" not in event
    assert event.get("livemode", True) is True
    with pytest.raises(AttributeError, match="no tiene el campo 'livemode'"):
        event.livemode
    assert event.to_dict() == EVENT_PAYMENT_SUCCEEDED


def test_list_object_iterates_its_data() -> None:
    page = convert_to_raya_object(TRANSFER_LIST)
    assert type(page) is rayacash.ListObject
    assert [t.id for t in page] == [TRANSFER_LIST["data"][0]["id"], TRANSFER_LIST["data"][1]["id"]]
    assert len(page) == 2
    assert next(reversed(page)).id == TRANSFER_LIST["data"][1]["id"]
    assert all(type(t) is rayacash.Transfer for t in page.data)
    assert page["has_more"] is True
    assert page.next_cursor == TRANSFER_LIST["next_cursor"]
    assert json.loads(json.dumps(page)) == TRANSFER_LIST
    assert dict(page) == page.to_dict() == TRANSFER_LIST
    with pytest.raises(KeyError, match=r"page.data\[0\]"):
        page[0]  # type: ignore[index]


def test_list_object_without_data() -> None:
    page: rayacash.ListObject[Any] = rayacash.ListObject.construct_from({"object": "list"})
    assert list(page) == []
    assert len(page) == 0


# --- Raya Connect: ConnectOrder, User y OAuthToken ---------------------------------------------


def test_connect_order_nested_objects_and_items() -> None:
    # "connect.order" lleva un punto: es una sola clave del registro, no "connect" + "order".
    pending = convert_to_raya_object(ORDER_PENDING)
    assert type(pending) is rayacash.ConnectOrder
    assert pending.object == "connect.order"
    assert type(pending.bank_transfer) is rayacash.ConnectOrder.BankTransfer
    assert type(pending.back_urls) is rayacash.ConnectOrder.BackUrls
    assert pending.back_urls.failure == "https://tienda.example.com/pedidos/1042/error"
    assert pending.payer is None
    assert pending.auto_return == "approved"
    assert pending.notification_url == NOTIFICATION_URL
    assert type(pending.metadata) is dict  # dict común: las claves son tuyas
    # Los ítems se leen con order["items"]: order.items es el método items() de dict.
    items = pending["items"]
    assert [type(item) for item in items] == [rayacash.ConnectOrder.Item]
    assert items[0].title == "Pedido 1042"
    assert items[0].quantity == 1
    assert items[0].unit_price == 45000
    assert callable(pending.items)
    assert dict(pending.items()) == pending

    succeeded = convert_to_raya_object(ORDER_SUCCEEDED)
    assert type(succeeded.payer) is rayacash.ConnectOrder.Payer
    assert succeeded.payer.name == "María Ejemplo"
    assert succeeded.to_dict() == ORDER_SUCCEEDED
    assert type(succeeded.to_dict()["items"][0]) is dict
    assert json.loads(json.dumps(succeeded)) == ORDER_SUCCEEDED
    assert repr(succeeded).startswith(f"<ConnectOrder connect.order id={ORDER_ID} at 0x")


def test_connect_payout_nested_objects() -> None:
    # "connect.payout" lleva un punto: es una sola clave del registro, como "connect.order".
    payout = convert_to_raya_object(PAYOUT_PENDING)
    assert type(payout) is rayacash.ConnectPayout
    assert payout.object == "connect.payout"
    assert type(payout.origin) is rayacash.ConnectPayout.Origin
    assert payout.origin.account == PAYOUT_ORIGIN_ACCOUNT
    assert payout.origin.alias == "raya.cash.ejemplo"
    assert type(payout.counterparty) is rayacash.ConnectPayout.Counterparty
    assert payout.counterparty.account == PAYOUT_DESTINATION
    assert isinstance(payout.processing_fee, float)
    assert payout.reference is None
    assert payout.to_dict() == PAYOUT_PENDING
    assert type(payout.to_dict()["origin"]) is dict
    assert json.loads(json.dumps(payout)) == PAYOUT_PENDING
    assert repr(payout).startswith(f"<ConnectPayout connect.payout id={PAYOUT_ID} at 0x")

    completed = convert_to_raya_object(PAYOUT_COMPLETED)
    assert completed.reference == "M7Q2X9T4K1V6N3B8R5W0ZD"

    restored = pickle.loads(pickle.dumps(payout))
    assert type(restored) is rayacash.ConnectPayout
    assert type(restored.origin) is rayacash.ConnectPayout.Origin
    assert restored == payout


def test_a_page_of_connect_payouts() -> None:
    page = convert_to_raya_object(PAYOUT_LIST)
    assert type(page) is rayacash.ListObject
    assert [type(payout) for payout in page] == [rayacash.ConnectPayout]
    assert json.loads(json.dumps(page)) == PAYOUT_LIST


def test_user_nested_objects() -> None:
    user = convert_to_raya_object(USER)
    assert type(user) is rayacash.User
    assert user.type == "personal"
    assert type(user.identification) is rayacash.User.Identification
    assert user.identification.number == "34567890"
    assert type(user.address) is rayacash.User.Address
    assert user.address.postal_code == "2000"
    assert type(user.merchant) is rayacash.User.Merchant
    assert user.merchant.image is None
    assert user.business is None
    assert user.identity_verified is True
    assert user.to_dict() == USER

    business = convert_to_raya_object(USER_BUSINESS)
    assert business.type == "business"
    assert type(business.business) is rayacash.User.Business
    assert type(business.business.representative) is rayacash.User.Business.Representative
    assert business.business.representative.tax_id == "20123456785"
    assert business.identification.type == "CUIT"
    assert business.address is None
    assert business.merchant is None
    assert json.loads(json.dumps(business)) == USER_BUSINESS


def test_oauth_token_masks_the_token_in_str_and_repr() -> None:
    token = convert_to_raya_object(OAUTH_TOKEN)
    assert type(token) is rayacash.OAuthToken
    assert token.access_token == ACCESS_TOKEN
    assert token.expires_in is None
    assert token.refresh_token is None
    text = str(token)
    assert ACCESS_TOKEN not in text
    assert ACCESS_TOKEN not in repr(token)
    assert json.loads(text)["access_token"] == "raya_at_live_…fG9h"
    assert json.loads(text)["user_id"] == USER_ID
    # Para guardarlo o mandarlo: el valor entero.
    assert token.to_dict() == OAUTH_TOKEN
    assert json.loads(json.dumps(token)) == OAUTH_TOKEN
    empty = rayacash.OAuthToken.construct_from({"object": "oauth_token"})
    assert str(empty) == '{\n  "object": "oauth_token"\n}'


def test_oauth_token_masks_a_sandbox_access_token_with_its_prefix() -> None:
    # El de un usuario de prueba de un sandbox (raya_at_test_…): la misma máscara, con su prefijo.
    values = {**OAUTH_TOKEN, "access_token": SANDBOX_ACCESS_TOKEN}
    token = rayacash.OAuthToken.construct_from(values)
    assert token.access_token == SANDBOX_ACCESS_TOKEN
    assert json.loads(str(token))["access_token"] == "raya_at_test_…L0sA"
    assert SANDBOX_ACCESS_TOKEN not in str(token)
    assert SANDBOX_ACCESS_TOKEN not in repr(token)
    assert token.to_dict() == values  # para guardarlo, entero


def test_event_hydrates_a_connect_order() -> None:
    event = rayacash.Event.construct_from(EVENT_ORDER_SUCCEEDED)
    assert event.type == "connect.order.succeeded"
    assert type(event.data.object) is rayacash.ConnectOrder
    assert event.data.object.net_amount == 44500
    assert event.to_dict() == EVENT_ORDER_SUCCEEDED


# --- Identidad: IdentityVerification e IdentityVerificationFiles ---------------------------------


def test_identity_classes_are_registered_by_their_whole_object_name() -> None:
    # "identity.verification" lleva un punto: es una sola clave del registro, como "connect.order".
    assert OBJECT_CLASSES["identity.verification"] is rayacash.IdentityVerification
    assert OBJECT_CLASSES["identity.verification_files"] is rayacash.IdentityVerificationFiles
    assert rayacash.IdentityVerification.OBJECT_NAME == "identity.verification"
    assert rayacash.IdentityVerificationFiles.OBJECT_NAME == "identity.verification_files"
    assert type(convert_to_raya_object({"object": "identity"})) is rayacash.RayaObject


def test_identity_verification_nested_objects() -> None:
    verification = convert_to_raya_object(VERIFICATION_VERIFIED)
    assert type(verification) is rayacash.IdentityVerification
    assert verification.object == "identity.verification"
    assert verification.id == VERIFICATION_ID
    checks = verification.checks
    assert type(checks) is rayacash.IdentityVerification.Checks
    assert type(checks.document) is rayacash.IdentityVerification.DocumentCheck
    assert checks.document.status == "passed"
    assert type(checks.liveness) is rayacash.IdentityVerification.LivenessCheck
    assert checks.liveness.confidence == 99.1
    assert type(checks.face_match) is rayacash.IdentityVerification.FaceMatchCheck
    assert checks.face_match.similarity == 97.4
    assert type(checks.registry) is rayacash.IdentityVerification.RegistryCheck
    assert checks.registry.data_match is True
    assert checks.registry.face_match == "hit"
    person = verification.person
    assert type(person) is rayacash.IdentityVerification.Person
    assert person.cuil == "27123456781"
    assert type(person.address) is rayacash.IdentityVerification.Address
    assert person.address.municipality == "Rosario"
    assert person.address.floor is None
    assert type(person.document) is rayacash.IdentityVerification.IdentityDocument
    assert person.document.expiry_date == "2035-01-31"
    # El ejemplar se lee con document["copy"]: document.copy es el método copy() de dict.
    assert person.document["copy"] == "A"
    assert callable(person.document.copy)
    assert person.document.copy() == PERSON["document"]
    assert verification.decline_reason is None
    assert type(verification.metadata) is dict  # dict común: las claves son tuyas
    assert isinstance(verification.amount, int)
    assert verification.currency == "ARS"
    assert repr(verification).startswith(
        f"<IdentityVerification identity.verification id={VERIFICATION_ID} at 0x"
    )

    declined = convert_to_raya_object(VERIFICATION_DECLINED)
    assert type(declined.decline_reason) is rayacash.IdentityVerification.DeclineReason
    assert declined.decline_reason.code == "registry_data_mismatch"
    assert declined.checks.registry.data_match is False
    assert declined.person is None

    biometric = convert_to_raya_object(VERIFICATION_BIOMETRIC_VERIFIED)
    assert biometric.type == "biometric"
    assert biometric.reference == VERIFICATION_ID
    assert biometric.checks.document.status == "not_applicable"
    assert biometric.checks.registry.face_match is None


def test_identity_verification_values_stay_as_raw_json_in_their_order() -> None:
    verification = convert_to_raya_object(VERIFICATION_VERIFIED)
    assert list(verification) == list(VERIFICATION_VERIFIED)
    assert len(verification) == 19
    assert verification.to_dict() == VERIFICATION_VERIFIED
    assert type(verification.to_dict()["person"]["address"]) is dict
    assert json.loads(json.dumps(verification)) == VERIFICATION_VERIFIED
    assert json.loads(str(verification)) == VERIFICATION_VERIFIED


def test_identity_verification_metadata_keys_are_yours() -> None:
    metadata = {"object": "identity.verification", "keys": "x", "copy": "y"}
    verification = convert_to_raya_object({**VERIFICATION_PENDING, "metadata": metadata})
    assert type(verification.metadata) is dict
    assert verification.metadata == metadata


def test_identity_verification_unknown_fields_and_values_pass() -> None:
    data = {
        **VERIFICATION_PENDING,
        "status": "en_revision",
        "nuevo_campo": {"a": 1},
        "checks": {**VERIFICATION_PENDING["checks"], "nuevo_control": {"status": "pending"}},
    }
    verification = convert_to_raya_object(data)
    assert verification.status == "en_revision"
    assert verification["nuevo_campo"] == {"a": 1}
    assert type(verification.checks["nuevo_control"]) is rayacash.RayaObject
    assert verification.to_dict() == data


def test_identity_verification_pickle_copy_and_deepcopy() -> None:
    verification = convert_to_raya_object(VERIFICATION_VERIFIED)
    restored = pickle.loads(pickle.dumps(verification))
    assert type(restored) is rayacash.IdentityVerification
    assert type(restored.checks.registry) is rayacash.IdentityVerification.RegistryCheck
    assert restored.person is not None
    assert type(restored.person.address) is rayacash.IdentityVerification.Address
    assert restored == verification
    assert restored._requestor is None

    deep = copy.deepcopy(verification)
    assert type(deep.person.document) is rayacash.IdentityVerification.IdentityDocument
    deep.metadata["plan"] = "otro"
    assert verification.metadata["plan"] == "pro"


def test_identity_verification_files() -> None:
    files = convert_to_raya_object(VERIFICATION_FILES)
    assert type(files) is rayacash.IdentityVerificationFiles
    assert files.object == "identity.verification_files"
    assert [type(files[name]) for name in ("front", "back", "selfie")] == [
        rayacash.IdentityVerificationFiles.File
    ] * 3
    assert files.back is not None
    assert files.back.url.endswith("/back.jpg?signature=ejemplo")
    assert files.to_dict() == VERIFICATION_FILES
    assert json.loads(json.dumps(files)) == VERIFICATION_FILES
    # Una biometric solo tiene selfie: las demás vienen en None.
    biometric = convert_to_raya_object({**VERIFICATION_FILES, "front": None, "back": None})
    assert biometric.front is None
    assert biometric.back is None
    assert type(biometric.selfie) is rayacash.IdentityVerificationFiles.File


def test_a_page_of_identity_verifications() -> None:
    page = convert_to_raya_object(VERIFICATION_LIST)
    assert type(page) is rayacash.ListObject
    assert [type(verification) for verification in page] == [rayacash.IdentityVerification] * 2
    assert json.loads(json.dumps(page)) == VERIFICATION_LIST


def test_event_hydrates_an_identity_verification() -> None:
    event = rayacash.Event.construct_from(EVENT_VERIFICATION_VERIFIED)
    assert event.type == "identity.verification.verified"
    verification = event.data.object
    assert type(verification) is rayacash.IdentityVerification
    assert verification.status == "verified"
    assert verification.person is None  # los eventos nunca traen person
    assert type(verification.checks) is rayacash.IdentityVerification.Checks
    assert event.livemode is True  # un evento de la cuenta real
    assert event.to_dict() == EVENT_VERIFICATION_VERIFIED


# --- Raya PSP: PspCustomer, PspCustomerBalance, PspTransfer, PspBalance y PspDocumentRequest ----

# Las claves de cada objeto, en el orden de la API (las tuplas *_KEYS de
# pspexternal/serializers.py): sin terms_accepted_at.
PSP_CUSTOMER_KEYS = [
    "id",
    "object",
    "status",
    "person_type",
    "tax_id",
    "name",
    "balance",
    "currency",
    "cvu",
    "blocked_by",
    "identity_verification",
    "decline_reason",
    "external_reference",
    "metadata",
    "created_at",
]
PSP_TRANSFER_KEYS = [
    "id",
    "object",
    "customer",
    "direction",
    "status",
    "amount",
    "fee",
    "net_amount",
    "currency",
    "account",
    "counterparty",
    "description",
    "reference",
    "created_at",
]


def fields_of(cls: type[rayacash.RayaObject]) -> list[str]:
    """Los campos que anota la clase, en orden (sin los ClassVar privados)."""
    return [name for name in vars(cls).get("__annotations__", {}) if not name.startswith("_")]


def test_psp_classes_are_registered_by_their_whole_object_name() -> None:
    # "psp.customer" lleva un punto: es una sola clave del registro, como "connect.order".
    classes = {
        "psp.balance": rayacash.PspBalance,
        "psp.customer": rayacash.PspCustomer,
        "psp.customer_balance": rayacash.PspCustomerBalance,
        "psp.document_request": rayacash.PspDocumentRequest,
        "psp.transfer": rayacash.PspTransfer,
    }
    for object_name, cls in classes.items():
        assert OBJECT_CLASSES[object_name] is cls
        assert object_name == cls.OBJECT_NAME
    assert type(convert_to_raya_object({"object": "psp"})) is rayacash.RayaObject
    assert type(convert_to_raya_object({"object": "psp.cliente"})) is rayacash.RayaObject


def test_psp_classes_annotate_the_fields_of_the_api_in_order() -> None:
    assert fields_of(rayacash.PspCustomer) == PSP_CUSTOMER_KEYS
    assert fields_of(rayacash.PspCustomer.Cvu) == [
        "account",
        "alias",
        "holder_name",
        "status",
        "created_at",
        "closed_at",
    ]
    assert fields_of(rayacash.PspCustomer.DeclineReason) == ["code", "message"]
    assert fields_of(rayacash.PspCustomerBalance) == [
        "object",
        "customer",
        "available",
        "transferable",
        "currency",
    ]
    assert fields_of(rayacash.PspTransfer) == PSP_TRANSFER_KEYS
    assert fields_of(rayacash.PspTransfer.Counterparty) == ["name", "tax_id", "account", "alias"]
    assert fields_of(rayacash.PspBalance) == [
        "object",
        "available",
        "customers_balance",
        "currency",
    ]
    assert fields_of(rayacash.PspDocumentRequest) == [
        "id",
        "object",
        "customer",
        "status",
        "subject",
        "message",
        "created_at",
        "submitted_at",
        "closed_at",
    ]
    assert list(psp.CUSTOMER_ACTIVE) == PSP_CUSTOMER_KEYS
    assert list(psp.TRANSFER_INBOUND) == PSP_TRANSFER_KEYS


def test_psp_customer_nested_objects() -> None:
    customer = convert_to_raya_object(psp.CUSTOMER_WITH_BALANCE)
    assert type(customer) is rayacash.PspCustomer
    assert customer.object == "psp.customer"
    assert customer.id == psp.CUSTOMER_ID
    assert customer.person_type == "F"
    assert customer.tax_id == psp.TAX_ID
    cvu = customer.cvu
    assert type(cvu) is rayacash.PspCustomer.Cvu
    assert cvu.account == psp.CUSTOMER_ACCOUNT
    assert cvu.holder_name == "MARIA LAURA EJEMPLO"
    assert cvu.status == "active"
    assert cvu.closed_at is None
    assert customer.blocked_by is None
    assert customer.decline_reason is None
    assert type(customer.metadata) is dict  # dict común: las claves son tuyas
    assert isinstance(customer.balance, float)
    assert repr(customer).startswith(f"<PspCustomer psp.customer id={psp.CUSTOMER_ID} at 0x")

    rejected = convert_to_raya_object(psp.CUSTOMER_REJECTED)
    assert type(rejected.decline_reason) is rayacash.PspCustomer.DeclineReason
    assert rejected.decline_reason.code == "face_mismatch"
    assert rejected.cvu is None

    blocked = convert_to_raya_object(psp.CUSTOMER_BLOCKED)
    assert (blocked.status, blocked.blocked_by) == ("blocked", "account")

    company = convert_to_raya_object(psp.COMPANY_VERIFYING)
    assert (company.person_type, company.status, company.metadata) == ("J", "verifying", {})


def test_psp_customer_values_stay_as_raw_json_in_their_order() -> None:
    customer = convert_to_raya_object(psp.CUSTOMER_ACTIVE)
    assert list(customer) == PSP_CUSTOMER_KEYS
    assert len(customer) == 15
    assert isinstance(customer.balance, int)  # 0, como vino
    assert customer.to_dict() == psp.CUSTOMER_ACTIVE
    assert type(customer.to_dict()["cvu"]) is dict
    assert json.loads(json.dumps(customer)) == psp.CUSTOMER_ACTIVE
    assert json.loads(str(customer)) == psp.CUSTOMER_ACTIVE


def test_psp_customer_metadata_keys_are_yours() -> None:
    metadata = {"object": "psp.customer", "keys": "x", "block": "y", "cvu": "z"}
    customer = convert_to_raya_object({**psp.CUSTOMER_ACTIVE, "metadata": metadata})
    assert type(customer.metadata) is dict
    assert customer.metadata == metadata


def test_psp_customer_actions_are_not_fields() -> None:
    # block, unblock, close y recreate son métodos: un campo con ese nombre se lee con [].
    customer = convert_to_raya_object({**psp.CUSTOMER_ACTIVE, "close": "valor"})
    assert callable(customer.close)
    assert customer["close"] == "valor"
    for action in ("block", "unblock", "close", "recreate"):
        assert callable(getattr(customer, action))
        assert callable(getattr(customer, f"{action}_async"))
        assert action not in fields_of(rayacash.PspCustomer)


def test_psp_customer_unknown_fields_and_values_pass() -> None:
    data = {
        **psp.CUSTOMER_ACTIVE,
        "status": "en_revision",
        "nuevo_campo": {"a": 1},
        "cvu": {**psp.CUSTOMER_ACTIVE["cvu"], "status": "suspended", "bank": "x"},
        "decline_reason": {"code": "nuevo_motivo", "message": "Otro motivo."},
    }
    customer = convert_to_raya_object(data)
    assert customer.status == "en_revision"
    assert customer["nuevo_campo"] == {"a": 1}
    assert type(customer.cvu) is rayacash.PspCustomer.Cvu
    assert customer.cvu["status"] == "suspended"  # un estado que el SDK todavía no conoce
    assert customer.decline_reason.code == "nuevo_motivo"
    assert customer.to_dict() == data


def test_psp_customer_pickle_copy_and_deepcopy() -> None:
    customer = convert_to_raya_object(psp.CUSTOMER_REJECTED)
    restored = pickle.loads(pickle.dumps(customer))
    assert type(restored) is rayacash.PspCustomer
    assert type(restored.decline_reason) is rayacash.PspCustomer.DeclineReason
    assert restored == customer
    assert restored._requestor is None

    active = convert_to_raya_object(psp.CUSTOMER_ACTIVE)
    deep = copy.deepcopy(active)
    assert type(deep.cvu) is rayacash.PspCustomer.Cvu
    deep.metadata["plan"] = "otro"
    assert active.metadata["plan"] == "pro"
    assert type(copy.copy(active)) is rayacash.PspCustomer


def test_psp_customer_balance_and_psp_balance() -> None:
    balance = convert_to_raya_object(psp.CUSTOMER_BALANCE)
    assert type(balance) is rayacash.PspCustomerBalance
    assert (balance.customer, balance.available, balance.transferable) == (
        psp.CUSTOMER_ID,
        23649.5,
        23649.5,
    )
    assert "id" not in balance  # sin id, como balance
    assert repr(balance).startswith("<PspCustomerBalance psp.customer_balance at 0x")
    totals = convert_to_raya_object(psp.PSP_BALANCE)
    assert type(totals) is rayacash.PspBalance
    assert (totals.available, totals.customers_balance) == (640200.5, 512875.25)
    # Tu saldo puede ser negativo: el número viaja como vino.
    negative = convert_to_raya_object({**psp.PSP_BALANCE, "available": -1500.75})
    assert negative.available == -1500.75
    assert totals.to_dict() == psp.PSP_BALANCE


def test_psp_transfer_nested_objects() -> None:
    transfer = convert_to_raya_object(psp.TRANSFER_INBOUND)
    assert type(transfer) is rayacash.PspTransfer
    assert list(transfer) == PSP_TRANSFER_KEYS
    assert (transfer.amount, transfer.fee, transfer.net_amount) == (42000, 133.9, 41866.1)
    assert type(transfer.counterparty) is rayacash.PspTransfer.Counterparty
    assert transfer.counterparty.name == "Juan Ejemplo"
    assert transfer.counterparty.alias is None
    assert transfer.account == psp.CUSTOMER_ACCOUNT
    assert transfer.reference == "H6T2Y9P4W1K7N3X8Q5R0ZB"
    assert transfer.to_dict() == psp.TRANSFER_INBOUND
    assert repr(transfer).startswith(f"<PspTransfer psp.transfer id={psp.INBOUND_ID} at 0x")
    # No es un Transfer: las de tus clientes no aparecen en transfers.list().
    assert not isinstance(transfer, rayacash.Transfer)
    restored = pickle.loads(pickle.dumps(transfer))
    assert type(restored.counterparty) is rayacash.PspTransfer.Counterparty


def test_psp_document_request() -> None:
    request = convert_to_raya_object(psp.DOCUMENT_REQUEST_OPEN)
    assert type(request) is rayacash.PspDocumentRequest
    assert request.object == "psp.document_request"
    assert request.customer == psp.CUSTOMER_ID
    assert request.status == "open"
    assert request.submitted_at is None
    assert request.to_dict() == psp.DOCUMENT_REQUEST_OPEN
    closed = convert_to_raya_object(psp.DOCUMENT_REQUEST_CLOSED)
    assert (closed.status, closed.closed_at) == ("closed", "2026-10-26T09:00:00Z")


def test_a_page_of_psp_customers_and_transfers() -> None:
    customers = convert_to_raya_object(psp.CUSTOMER_LIST)
    assert type(customers) is rayacash.ListObject
    assert [type(customer) for customer in customers] == [rayacash.PspCustomer] * 2
    assert json.loads(json.dumps(customers)) == psp.CUSTOMER_LIST
    transfers = convert_to_raya_object(psp.TRANSFER_LIST)
    assert [type(transfer) for transfer in transfers] == [rayacash.PspTransfer] * 2


@pytest.mark.parametrize(
    ("event", "cls"),
    [
        (psp.EVENT_CUSTOMER_ACTIVATED, rayacash.PspCustomer),
        (psp.EVENT_TRANSFER_RECEIVED, rayacash.PspTransfer),
        (psp.EVENT_DOCUMENT_REQUEST_CREATED, rayacash.PspDocumentRequest),
    ],
    ids=["customer", "transfer", "document_request"],
)
def test_event_hydrates_psp_objects(event: dict[str, Any], cls: type[rayacash.RayaObject]) -> None:
    hydrated = rayacash.Event.construct_from(event)
    assert hydrated.type == event["type"]
    assert type(hydrated.data.object) is cls
    assert hydrated.to_dict() == event
