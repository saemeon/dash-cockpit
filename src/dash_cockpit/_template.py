"""Card templates — parametrizable factories for runtime-built cards.

Where a :class:`Card` is one fixed widget, a :class:`CardTemplate` is a
recipe: pick a template, fill in parameters, get a card. Used by
:class:`ConfiguratorPage` to let users assemble pages on the fly.

Two pieces of plumbing live here:

- :func:`card_id_for` — deterministic ID derived from ``(template_id, params)``
  so that adding the same template twice with the same parameters is
  idempotent.
- :func:`fanout_params` — expands ``multi_select`` parameters into the
  cartesian product of single-value param dicts, so one user click can
  spawn N cards (e.g. one KPI per division).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dash_cockpit._card import Card


ParameterType = Literal["select", "multi_select", "number", "date", "text"]
"""Widget kind for one ``ParameterSpec``. Drives form rendering."""


@dataclass(frozen=True)
class ParameterSpec:
    """One field in a template's parameter form.

    Parameters
    ----------
    name : str
        Machine name, used as the key in the resulting ``params`` dict.
    label : str
        Human-readable label shown above the input.
    type : ParameterType
        Widget kind. ``"multi_select"`` triggers fan-out (one card per value).
    options : list, optional
        Static option list for ``select`` / ``multi_select``. Ignored if
        ``options_fn`` is provided. By default ``None``.
    options_fn : Callable[[dict], list], optional
        Cascading-options callback. Receives the current param dict and
        returns the option list. Re-evaluated on every form change.
        Takes precedence over ``options`` when set. By default ``None``.
    default : Any, optional
        Pre-filled value (or list, for ``multi_select``). By default ``None``.
    required : bool, optional
        If ``True`` (default), the configurator's "Add" button surfaces a
        "Missing required: ..." status until the field has a value.

    Examples
    --------
    Cascading dropdown — available metrics depend on the chosen year::

        ParameterSpec(
            name="metric",
            label="Metric",
            type="select",
            options_fn=lambda p: METRICS_BY_YEAR.get(p.get("year"), []),
        )
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
    """Metadata every template declares on its ``TEMPLATE_META`` attribute.

    Parameters
    ----------
    id : str
        Globally-unique template ID. Used in ``ConfiguratorPage.template_ids``
        and as input to :func:`card_id_for`.
    title : str
        Human-readable title shown in the template picker.
    team : str
        Owning team's machine name.
    description : str
        Short prose description.
    category : str
        Free-form category tag.
    parameters : list[ParameterSpec], optional
        Form fields shown to the user. Empty list means a parameter-less
        template (one button click instantiates it). By default ``[]``.
    """

    id: str
    title: str
    team: str
    description: str
    category: str
    parameters: list[ParameterSpec] = field(default_factory=list)


@runtime_checkable
class CardTemplate(Protocol):
    """Protocol for parametrizable card factories.

    Attributes
    ----------
    TEMPLATE_META : TemplateMeta
        Required class- or instance-level metadata. Validated at registration.

    Notes
    -----
    Implementations should return a fresh :class:`Card` from each
    ``instantiate`` call — the cockpit may call this many times per session.
    """

    TEMPLATE_META: TemplateMeta

    def instantiate(self, params: dict[str, Any]) -> Card:
        """Return a fully-formed :class:`Card` for the given parameters.

        Parameters
        ----------
        params : dict
            Parameter values matching the template's ``ParameterSpec`` list.
            For ``multi_select`` parameters, the cockpit calls this once per
            scalar value (see :func:`fanout_params`).

        Returns
        -------
        Card
            The instantiated card. Its ``CARD_META["id"]`` is overwritten by
            the configurator with a deterministic id derived from
            ``(template_id, params)``, so callers do not need to compute it.
        """
        ...


def _stable_hash(params: dict[str, Any]) -> str:
    """Order-independent SHA1 prefix of a JSON-serialisable params dict."""
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def card_id_for(template_id: str, params: dict[str, Any]) -> str:
    """Deterministic card ID for a ``(template, params)`` pair.

    Used by the configurator to deduplicate the working list — clicking
    "Add" with the same parameters twice is a no-op rather than producing
    two identical cards.

    Parameters
    ----------
    template_id : str
        The template's ``TEMPLATE_META.id``.
    params : dict
        Parameter values. Order-independent (sorted keys).

    Returns
    -------
    str
        ``"{template_id}-{10-char-hash}"``.
    """
    return f"{template_id}-{_stable_hash(params)}"


def fanout_params(
    template: CardTemplate, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Expand ``multi_select`` parameters into one params dict per scalar value.

    Multi-selects in templates exist so a single user gesture can spawn
    multiple cards — typical case: "show me KPI X for divisions A, B, C"
    becomes three cards. With more than one ``multi_select`` the result is
    the cartesian product.

    Parameters
    ----------
    template : CardTemplate
        Template defining the parameter shape.
    params : dict
        Raw parameter dict from the form. ``multi_select`` values may be a
        list or a single value.

    Returns
    -------
    list[dict]
        One params dict per generated card. ``[]`` if any ``multi_select``
        was empty (no cards are produced for an empty selection).

    Examples
    --------
    >>> # Template has one multi_select named "division"
    >>> fanout_params(tpl, {"year": 2025, "division": ["A", "B"]})
    [{'year': 2025, 'division': 'A'}, {'year': 2025, 'division': 'B'}]
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
