"""Page-level layout dispatch — turns a :class:`Page` into a Dash component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dash import html

from dash_cockpit._chrome import card_chrome
from dash_cockpit._configurator import render_configurator
from dash_cockpit._error import error_boundary
from dash_cockpit._packing import pack_grid, pack_row
from dash_cockpit._page import ConfiguratorPage, Page, TeamPage
from dash_cockpit._refresh import wrap_for_refresh

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._presets import PresetStore
    from dash_cockpit._registry import CardRegistry


def _card_size(card_id: str, registry: CardRegistry) -> tuple[int, int]:
    """Return the ``(w, h)`` grid-unit size from ``CARD_META``, default ``(1, 1)``."""
    try:
        entry = registry.get(card_id)
    except KeyError:
        return (1, 1)
    size = entry["meta"].get("size")
    if size is None:
        return (1, 1)
    w, h = size
    return (max(1, int(w)), max(1, int(h)))


def _resolve_card(card_id: str, registry: CardRegistry, context: dict) -> Component:
    """Resolve and render one card, wrap in chrome, or warn if unknown."""
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
    meta = entry["meta"]
    card_obj = _CardShim(entry["render"], meta)
    body = error_boundary(card_obj, context)
    refresh_interval = meta.get("refresh_interval", 0)
    body = wrap_for_refresh(body, card_id, refresh_interval)
    return card_chrome(
        body,
        card_id=card_id,
        title=meta.get("title", ""),
        actions=meta.get("actions"),
    )


class _CardShim:
    """Minimal :class:`Card`-like wrapper around a registry entry.

    Lets :func:`error_boundary` accept a registry entry without forcing the
    registry to retain the original :class:`Card` object on the render path.
    """

    def __init__(self, render_fn, meta):
        self.CARD_META = meta
        self._render_fn = render_fn

    def render(self, context: dict) -> Component:
        return self._render_fn(context)


def render_page(
    page: Page,
    registry: CardRegistry,
    context: dict | None = None,
    *,
    preset_store: PresetStore | None = None,
) -> Component:
    """Render any concrete :class:`Page` into a Dash component.

    Dispatches by page type:

    - :class:`TeamPage` → drag-drop :class:`~dash_snap_grid.Grid` with
      per-card sizes from ``CARD_META["size"]`` and localStorage persistence.
    - :class:`UserPage` → fixed Bootstrap rows from the explicit 2D layout
      (no drag-drop, no persistence).
    - :class:`ConfiguratorPage` → forwarded to :func:`render_configurator`,
      with optional ``preset_store`` for the preset library UI.

    Parameters
    ----------
    page : Page
        The page to render.
    registry : CardRegistry
        Registry used to resolve card IDs and read ``CARD_META``.
    context : dict, optional
        Render context passed to each card's ``render``. Treated as ``{}``
        when ``None``. By default ``None``.
    preset_store : PresetStore, optional
        Forwarded to :func:`render_configurator` for ``ConfiguratorPage``.
        Ignored for other page types. By default ``None``.

    Returns
    -------
    Component
        A Dash component ready to insert into a Dash layout.
    """
    if context is None:
        context = {}

    if isinstance(page, ConfiguratorPage):
        return render_configurator(page, registry, preset_store=preset_store)

    if isinstance(page, TeamPage):
        components = [_resolve_card(cid, registry, context) for cid in page.card_ids]
        sizes = [_card_size(cid, registry) for cid in page.card_ids]
        return pack_grid(
            components,
            ids=list(page.card_ids),
            columns=page.columns,
            persist_key=f"team-v2:{page.name}",
            sizes=sizes,
        )

    # UserPage: 2D layout, each row may have a different number of cards.
    rendered_rows = [
        pack_row([_resolve_card(cid, registry, context) for cid in row])
        for row in page.layout
    ]
    return html.Div(rendered_rows)
