from __future__ import annotations

import importlib
from typing import Any

from dash_cockpit._card import Card, CardMeta
from dash_cockpit._template import CardTemplate

_REQUIRED_META_FIELDS = frozenset(CardMeta.__required_keys__)


class RegistryError(Exception):
    pass


class CardRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, dict[str, Any]] = {}
        self._templates: dict[str, CardTemplate] = {}

    def register(self, card: Card) -> None:
        meta = card.CARD_META
        missing = _REQUIRED_META_FIELDS - set(meta)
        if missing:
            raise RegistryError(f"Card missing metadata fields: {missing}")
        card_id = meta["id"]
        if card_id in self._registry:
            raise RegistryError(f"Duplicate card id: {card_id!r}")
        self._registry[card_id] = {"render": card.render, "meta": meta, "card": card}

    def register_template(self, template: CardTemplate) -> None:
        meta = template.TEMPLATE_META
        if meta.id in self._templates:
            raise RegistryError(f"Duplicate template id: {meta.id!r}")
        self._templates[meta.id] = template

    def load_package(self, package_name: str) -> list[str]:
        """Import a team package, call get_cards() and (optionally) get_card_templates().

        Returns registered card IDs (templates are registered but not in the returned list).
        """
        try:
            mod = importlib.import_module(package_name)
        except ImportError as e:
            raise RegistryError(f"Cannot import team package {package_name!r}: {e}") from e
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
        for name in package_names:
            self.load_package(name)

    def get(self, card_id: str) -> dict[str, Any]:
        if card_id not in self._registry:
            raise KeyError(f"Card {card_id!r} not in registry")
        return self._registry[card_id]

    def get_template(self, template_id: str) -> CardTemplate:
        if template_id not in self._templates:
            raise KeyError(f"Template {template_id!r} not registered")
        return self._templates[template_id]

    def all_ids(self) -> list[str]:
        return list(self._registry)

    def all_template_ids(self) -> list[str]:
        return list(self._templates)

    def by_team(self, team: str) -> list[str]:
        return [cid for cid, v in self._registry.items() if v["meta"]["team"] == team]

    def by_category(self, category: str) -> list[str]:
        return [cid for cid, v in self._registry.items() if v["meta"]["category"] == category]

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, card_id: object) -> bool:
        return card_id in self._registry
