"""RayaObject: un dict con acceso por atributo, como el StripeObject clásico.

Es un ``dict`` de verdad, con los valores tal como vienen en el JSON de la API (montos int o
float, fechas en string ISO), así que ``json.dumps(obj)`` anda. Los campos que el SDK todavía
no conoce también quedan: la API puede sumar campos y tu código tiene que ignorarlos.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from typing_extensions import Self

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor
    from rayacash._response import RayaResponse


class RayaObject(dict[str, Any]):
    """Un objeto de la API. ``obj.campo`` y ``obj["campo"]`` dan lo mismo."""

    #: El valor de ``object`` que identifica a la clase (``"payment"``, ``"transfer"``…).
    OBJECT_NAME: ClassVar[str | None] = None
    #: Clase de los sub-objetos sin ``object`` propio (por ejemplo, ``counterparty``).
    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {}
    #: Campos que quedan como dict plano: sus claves son tuyas (``metadata``).
    _plain_fields: ClassVar[frozenset[str]] = frozenset()

    _requestor: APIRequestor | None
    _last_response: RayaResponse | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_requestor", None)
        object.__setattr__(self, "_last_response", None)

    if not TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any:
            if name.startswith("_"):
                raise AttributeError(name)
            try:
                return self[name]
            except KeyError:
                raise AttributeError(
                    f"{type(self).__name__} no tiene el campo {name!r}. "
                    f"Campos: {', '.join(sorted(self.keys())) or '(ninguno)'}."
                ) from None

        def __setattr__(self, name: str, value: Any) -> None:
            if name.startswith("_"):
                object.__setattr__(self, name, value)
            else:
                self[name] = value

        def __delattr__(self, name: str) -> None:
            if name.startswith("_"):
                object.__delattr__(self, name)
                return
            try:
                del self[name]
            except KeyError:
                raise AttributeError(name) from None

    @classmethod
    def construct_from(
        cls,
        values: Mapping[str, Any],
        *,
        requestor: APIRequestor | None = None,
        last_response: RayaResponse | None = None,
    ) -> Self:
        """Arma el objeto (y sus sub-objetos) desde el JSON de la API."""
        obj = cls()
        object.__setattr__(obj, "_requestor", requestor)
        object.__setattr__(obj, "_last_response", last_response)
        for key, value in values.items():
            dict.__setitem__(obj, key, cls._convert_field(key, value, requestor))
        return obj

    @classmethod
    def _convert_field(cls, key: str, value: Any, requestor: APIRequestor | None) -> Any:
        if key in cls._plain_fields:
            return _to_plain(value)
        return convert_to_raya_object(value, requestor, cls._inner_class_types.get(key))

    @property
    def last_response(self) -> RayaResponse | None:
        """La respuesta HTTP que trajo este objeto (``request_id``, headers…)."""
        return self._last_response

    def to_dict(self) -> dict[str, Any]:
        """Un dict plano (recursivo), sin las clases del SDK."""
        return _to_plain(self)  # type: ignore[no-any-return]

    def _resolve_requestor(self) -> APIRequestor:
        if self._requestor is not None:
            return self._requestor
        from rayacash._global import default_requestor

        return default_requestor()

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        parts = [type(self).__name__]
        object_name = self.get("object")
        if isinstance(object_name, str):
            parts.append(object_name)
        object_id = self.get("id")
        if isinstance(object_id, str):
            parts.append(f"id={object_id}")
        return f"<{' '.join(parts)} at {hex(id(self))}> JSON: {self}"

    # pickle descarta el requestor (tiene clientes httpx); copy y deepcopy lo conservan.
    def __reduce__(self) -> Any:
        return (_reconstruct, (type(self), dict.copy(self)))

    def __copy__(self) -> Self:
        return type(self).construct_from(
            dict.copy(self), requestor=self._requestor, last_response=self._last_response
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        values = copy.deepcopy(dict.copy(self), memo)
        return type(self).construct_from(
            values, requestor=self._requestor, last_response=self._last_response
        )


def _reconstruct(cls: type[RayaObject], values: dict[str, Any]) -> RayaObject:
    return cls.construct_from(values)


def _to_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in dict.items(value)}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def get_object_class(object_name: str) -> type[RayaObject] | None:
    from rayacash._object_classes import OBJECT_CLASSES

    return OBJECT_CLASSES.get(object_name)


def convert_to_raya_object(
    value: Any,
    requestor: APIRequestor | None = None,
    default_class: type[RayaObject] | None = None,
) -> Any:
    """Convierte el JSON en objetos del SDK según su campo ``object`` (o la clase esperada)."""
    if isinstance(value, list):
        return [convert_to_raya_object(item, requestor, default_class) for item in value]
    if isinstance(value, dict):
        object_name = value.get("object")
        cls = get_object_class(object_name) if isinstance(object_name, str) else None
        if cls is None:
            cls = default_class or RayaObject
        return cls.construct_from(value, requestor=requestor)
    return value
