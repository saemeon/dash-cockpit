"""Startup-time registry of cards and templates loaded from team packages."""

from __future__ import annotations

import importlib
from typing import Any

from dash_cockpit._card import Card, CardMeta
from dash_cockpit._template import CardTemplate

_REQUIRED_META_FIELDS = frozenset(CardMeta.__required_keys__)


class RegistryError(Exception):
    """Raised when registration fails (duplicate id, missing metadata, import error)."""


class CardRegistry:
    """In-memory store of cards and templates published by team packages.

    The registry is the single source of truth the cockpit consults at render
    time. Populate it once at startup — typically by calling
    :meth:`load_packages` with the list of installed team packages — then
    pass it to :class:`CockpitApp`.

    Failure modes are intentionally loud at startup (raises
    :class:`RegistryError`) and quiet at render time (unknown card IDs
    render a warning tile). This trades surprises late for surprises early.

    Examples
    --------
    >>> from dash_cockpit import CardRegistry
    >>> registry = CardRegistry()
    >>> registry.load_packages(["team_finance", "team_ops"])
    >>> registry.all_ids()
    ['revenue_trend', 'cash_position', 'headcount', 'ticket_volume']
    >>> registry.by_team("finance")
    ['revenue_trend', 'cash_position']
    """

    def __init__(self) -> None:
        self._registry: dict[str, dict[str, Any]] = {}
        self._templates: dict[str, CardTemplate] = {}

    def register(self, card: Card) -> None:
        """Add a single card to the registry.

        Parameters
        ----------
        card : Card
            Any object satisfying the :class:`Card` protocol.

        Raises
        ------
        RegistryError
            If ``CARD_META`` is missing required fields, or another card with
            the same id is already registered.
        """
        meta = card.CARD_META
        missing = _REQUIRED_META_FIELDS - set(meta)
        if missing:
            raise RegistryError(f"Card missing metadata fields: {missing}")
        card_id = meta["id"]
        if card_id in self._registry:
            raise RegistryError(f"Duplicate card id: {card_id!r}")
        self._registry[card_id] = {"render": card.render, "meta": meta, "card": card}

    def register_template(self, template: CardTemplate) -> None:
        """Add a single card template to the registry.

        Parameters
        ----------
        template : CardTemplate
            Any object satisfying the :class:`CardTemplate` protocol.

        Raises
        ------
        RegistryError
            If a template with the same id is already registered.
        """
        meta = template.TEMPLATE_META
        if meta.id in self._templates:
            raise RegistryError(f"Duplicate template id: {meta.id!r}")
        self._templates[meta.id] = template

    def load_package(self, package_name: str) -> list[str]:
        """Import a team package and register the cards/templates it exposes.

        The package must define ``get_cards`` and/or ``get_card_templates``
        at its top level.

        Parameters
        ----------
        package_name : str
            Importable package name, e.g. ``"team_finance"``.

        Returns
        -------
        list[str]
            IDs of cards registered from this package. Templates are
            registered but not included in the returned list.

        Raises
        ------
        RegistryError
            If the package can't be imported, exposes neither hook, or any
            individual card/template registration fails.
        """
        try:
            mod = importlib.import_module(package_name)
        except ImportError as e:
            raise RegistryError(
                f"Cannot import team package {package_name!r}: {e}"
            ) from e
        if not hasattr(mod, "get_cards") and not hasattr(mod, "get_card_templates"):
            raise RegistryError(
                f"Package {package_name!r} has no get_cards() or get_card_templates() function"
            )
        ids = []
        if hasattr(mod, "get_cards"):
            for card in mod.get_cards():
                self.register(card)
                ids.append(card.CARD_META["id"])
        if hasattr(mod, "get_card_templates"):
            for tpl in mod.get_card_templates():
                self.register_template(tpl)
        return ids

    def load_packages(self, package_names: list[str]) -> None:
        """Load several team packages in order.

        Parameters
        ----------
        package_names : list[str]
            Importable package names. Loading is left-to-right; the first
            failure aborts and propagates.
        """
        for name in package_names:
            self.load_package(name)

    def get(self, card_id: str) -> dict[str, Any]:
        """Look up a card entry by id.

        Parameters
        ----------
        card_id : str
            The card's ``CARD_META["id"]``.

        Returns
        -------
        dict
            Mapping with ``render`` (the bound render function), ``meta``
            (the ``CARD_META`` dict), and ``card`` (the original object,
            used by export protocols).

        Raises
        ------
        KeyError
            If no card with that id is registered.
        """
        if card_id not in self._registry:
            raise KeyError(f"Card {card_id!r} not in registry")
        return self._registry[card_id]

    def get_template(self, template_id: str) -> CardTemplate:
        """Look up a template by id.

        Parameters
        ----------
        template_id : str
            The template's ``TEMPLATE_META.id``.

        Returns
        -------
        CardTemplate
            The registered template object.

        Raises
        ------
        KeyError
            If no template with that id is registered.
        """
        if template_id not in self._templates:
            raise KeyError(f"Template {template_id!r} not registered")
        return self._templates[template_id]

    def all_ids(self) -> list[str]:
        """Return all registered card IDs in registration order."""
        return list(self._registry)

    def all_template_ids(self) -> list[str]:
        """Return all registered template IDs in registration order."""
        return list(self._templates)

    def by_team(self, team: str) -> list[str]:
        """Return card IDs whose ``CARD_META["team"]`` matches ``team``."""
        return [cid for cid, v in self._registry.items() if v["meta"]["team"] == team]

    def by_category(self, category: str) -> list[str]:
        """Return card IDs whose ``CARD_META["category"]`` matches ``category``."""
        return [
            cid
            for cid, v in self._registry.items()
            if v["meta"]["category"] == category
        ]

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, card_id: object) -> bool:
        return card_id in self._registry
