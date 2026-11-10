from __future__ import annotations

import copy
import json
import pickle
from typing import Any

import pytest

import rayacash
from rayacash._raya_object import convert_to_raya_object
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
    TEST_MODE_ACCESS_TOKEN,
    USER,
    USER_BUSINESS,
    USER_ID,
)


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


def test_oauth_token_masks_a_test_mode_access_token_with_its_prefix() -> None:
    # El de la cuenta de prueba de una app (raya_at_test_…): la misma máscara, con su prefijo.
    values = {**OAUTH_TOKEN, "access_token": TEST_MODE_ACCESS_TOKEN}
    token = rayacash.OAuthToken.construct_from(values)
    assert token.access_token == TEST_MODE_ACCESS_TOKEN
    assert json.loads(str(token))["access_token"] == "raya_at_test_…L0sA"
    assert TEST_MODE_ACCESS_TOKEN not in str(token)
    assert TEST_MODE_ACCESS_TOKEN not in repr(token)
    assert token.to_dict() == values  # para guardarlo, entero


def test_event_hydrates_a_connect_order() -> None:
    event = rayacash.Event.construct_from(EVENT_ORDER_SUCCEEDED)
    assert event.type == "connect.order.succeeded"
    assert type(event.data.object) is rayacash.ConnectOrder
    assert event.data.object.net_amount == 44500
    assert event.to_dict() == EVENT_ORDER_SUCCEEDED
