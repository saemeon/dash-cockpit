from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dash_cockpit._card import Card


ParameterType = Literal["select", "multi_select", "number", "date", "text"]


@dataclass(frozen=True)
class ParameterSpec:
    """One field in a template's parameter form.

    Attributes:
        name: machine name; used as the dict key in `params`.
        label: display label shown in the form.
        type: one of "select", "multi_select", "number", "date", "text".
        options: static option list for select/multi_select.
        options_fn: dynamic option function `(other_params) -> list` for cascading dropdowns.
            Takes precedence over `options` when set.
        default: default value (single value, or list for multi_select).
        required: if True, "Add" is disabled until the field has a value.
    """

    name: str
    label: str
    type: ParameterType
    options: list[Any] | None = None
    options_fn: Callable[[dict[str, Any]], list[Any]] | None = None
    default: Any = None
    required: bool = True


@dataclass(frozen=True)
class TemplateMeta:
    id: str
    title: str
    team: str
    description: str
    category: str
    parameters: list[ParameterSpec] = field(default_factory=list)


@runtime_checkable
class CardTemplate(Protocol):
    """A parametrizable factory: instantiate(params) -> Card."""

    TEMPLATE_META: TemplateMeta

    def instantiate(self, params: dict[str, Any]) -> "Card": ...


def _stable_hash(params: dict[str, Any]) -> str:
    """Deterministic short hash of a params dict — order-independent, JSON-serialisable values."""
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def card_id_for(template_id: str, params: dict[str, Any]) -> str:
    """Deterministic card ID for a `(template, params)` pair. Used to deduplicate working lists."""
    return f"{template_id}-{_stable_hash(params)}"


def fanout_params(
    template: CardTemplate, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Expand multi_select params into one params dict per scalar value.

    If multiple multi_selects are present, take the cartesian product. If a multi_select
    is empty, the result is empty (no instantiations).
    """
    multi = [
        p.name for p in template.TEMPLATE_META.parameters if p.type == "multi_select"
    ]
    if not multi:
        return [dict(params)]

    result: list[dict[str, Any]] = [dict(params)]
    for name in multi:
        values = params.get(name) or []
        if not isinstance(values, list):
            values = [values]
        if not values:
            return []
        new_result = []
        for base in result:
            for v in values:
                expanded = dict(base)
                expanded[name] = v
                new_result.append(expanded)
        result = new_result
    return result
