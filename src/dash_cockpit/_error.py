from __future__ import annotations

from typing import TYPE_CHECKING

from dash import html

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._card import Card


def error_boundary(card: "Card", context: dict) -> "Component":
    try:
        return card.render(context)
    except Exception as e:
        return _error_card(card.CARD_META["id"], str(e))


def _error_card(card_id: str, message: str) -> "Component":
    return html.Div(
        [
            html.Strong(f"[{card_id}] Error"),
            html.Pre(message, style={"whiteSpace": "pre-wrap", "fontSize": "0.8em"}),
        ],
        style={
            "border": "1px solid #dc3545",
            "borderRadius": "4px",
            "padding": "12px",
            "color": "#dc3545",
            "background": "#fff5f5",
        },
    )
