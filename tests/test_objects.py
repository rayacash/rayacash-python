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
