from __future__ import annotations

from typing import TYPE_CHECKING

from dash import html

from dash_cockpit._configurator import render_configurator
from dash_cockpit._error import error_boundary
from dash_cockpit._packing import pack_grid, pack_row
from dash_cockpit._page import ConfiguratorPage, Page, TeamPage, UserPage

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._registry import CardRegistry


def _resolve_card(card_id: str, registry: "CardRegistry", context: dict) -> "Component":
    try:
        entry = registry.get(card_id)
    except KeyError:
        return html.Div(
            f"Unknown card: {card_id!r}",
            style={
                "color": "#856404",
                "background": "#fff3cd",
                "padding": "8px",
                "borderRadius": "4px",
            },
        )
    card_obj = _CardShim(entry["render"], entry["meta"])
    return error_boundary(card_obj, context)


class _CardShim:
    """Minimal Card-like wrapper around a registry entry."""

    def __init__(self, render_fn, meta):
        self.CARD_META = meta
        self._render_fn = render_fn

    def render(self, context: dict) -> "Component":
        return self._render_fn(context)


def render_page(
    page: Page, registry: "CardRegistry", context: dict | None = None
) -> "Component":
    if context is None:
        context = {}

    if isinstance(page, ConfiguratorPage):
        return render_configurator(page, registry)

    if isinstance(page, TeamPage):
        components = [_resolve_card(cid, registry, context) for cid in page.card_ids]
        return pack_grid(components, columns=page.columns)

    # UserPage: 2D layout, each row may have a different number of cards
    rendered_rows = [
        pack_row([_resolve_card(cid, registry, context) for cid in row])
        for row in page.layout
    ]
    return html.Div(rendered_rows)
