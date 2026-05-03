"""Cockpit-owned card chrome — the standard frame around every card body.

The cockpit is responsible for the *look* of a card (border, rounded corners,
header bar with title and ⋮ menu). Teams provide only the *body* — the actual
content of the card. This guarantees visual consistency across teams and
removes "cards must use ``height: 100%``" footguns: the chrome owns the cell.

The card protocol from a team's perspective:

    CARD_META = {"id": "...", "title": "...", ...}
    def render(context: dict) -> Component:
        # return ONLY the body — no border, no title, no padding around the edge.
        # The cockpit draws the chrome around it.
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import dash_bootstrap_components as dbc
from dash import html

from dash_cockpit._packing import CARD_MENU_CLASS

if TYPE_CHECKING:
    from dash.development.base_component import Component


_CARD_STYLE = {
    "height": "100%",
    "display": "flex",
    "flexDirection": "column",
    "background": "#ffffff",
    "border": "1px solid #dee2e6",
    "borderRadius": "8px",
    "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.04)",
    "overflow": "hidden",
}

_HEADER_STYLE = {
    "display": "flex",
    "justifyContent": "space-between",
    "alignItems": "center",
    "padding": "8px 12px",
    "borderBottom": "1px solid #eef0f2",
    "flexShrink": 0,
    "fontSize": "0.95rem",
}

_BODY_STYLE = {
    "flex": "1",
    "padding": "12px",
    "overflow": "auto",
    "minHeight": "0",  # standard flexbox-overflow trick
}

_MENU_TOGGLE_STYLE = {
    "color": "#6c757d",
    "padding": "0 6px",
    "fontSize": "1.2rem",
    "lineHeight": "1",
    "border": "none",
    "background": "transparent",
    "boxShadow": "none",
}


def card_chrome(
    body: Component,
    *,
    card_id: str,
    title: str = "",
    actions: list[dict[str, Any]] | None = None,
    extra_menu_items: list[Component] | None = None,
) -> Component:
    """Wrap a card body in the standard cockpit chrome.

    The chrome supplies the border, rounded corners, header bar with title
    and ⋮ menu, and the body container that fills the remaining cell height.
    Teams should never style their card with these themselves — that's the
    cockpit's job.

    Parameters
    ----------
    body : Component
        The team-provided card body. May render anything Dash supports;
        will be placed inside a flex-fill, scrollable body container.
    card_id : str
        ``CARD_META["id"]``. Used for action callback ids.
    title : str, optional
        ``CARD_META["title"]`` — shown in the header. Empty string hides it.
    actions : list[dict], optional
        Per-card opt-in actions from ``CARD_META["actions"]``. Each entry
        is ``{"id": ..., "label": ...}``; rendered as a menu item firing a
        pattern-matching callback. By default ``None``.
    extra_menu_items : list[Component], optional
        Additional menu items appended after ``actions`` (e.g. a "Remove"
        item used by the configurator). By default ``None``.

    Returns
    -------
    Component
        A self-contained card tile filling its grid cell.
    """
    menu_items: list[Component] = [
        dbc.DropdownMenuItem(
            a.get("label", a.get("id")),
            id={
                "type": "_cockpit_card_action",
                "card_id": card_id,
                "action": a.get("id"),
            },
            n_clicks=0,
        )
        for a in actions or []
    ]
    if extra_menu_items:
        menu_items.extend(extra_menu_items)

    menu_block: Component
    if menu_items:
        menu_block = html.Div(
            dbc.DropdownMenu(
                label="⋮",
                children=menu_items,
                size="sm",
                color="link",
                align_end=True,
                toggle_style=_MENU_TOGGLE_STYLE,
            ),
            className=CARD_MENU_CLASS,
        )
    else:
        menu_block = html.Span()

    header = html.Div(
        [html.Strong(title) if title else html.Span(), menu_block],
        style=_HEADER_STYLE,
    )

    return html.Div(
        [header, html.Div(body, style=_BODY_STYLE)],
        style=_CARD_STYLE,
        className="cockpit-card",
    )
