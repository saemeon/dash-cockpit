"""Per-card error isolation — a broken card must not break the page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dash import html

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._card import Card, RenderContext


def error_boundary(card: Card, context: RenderContext) -> Component:
    """Render a card, returning an error placeholder if it raises.

    This is the cockpit's failure-isolation primitive. A bad card surfaces
    as a red placeholder tile rather than crashing the page or its peers.

    Parameters
    ----------
    card : Card
        Any object satisfying the :class:`Card` protocol.
    context : RenderContext
        Render context forwarded to ``card.render``. See :class:`RenderContext`.

    Returns
    -------
    Component
        Either the card's normal render output, or a red error tile carrying
        the card id and exception message.
    """
    try:
        return card.render(context)
    except Exception as e:
        return _error_card(card.CARD_META["id"], str(e))


def _error_card(card_id: str, message: str) -> Component:
    """Build the red placeholder tile shown when a card's render raises."""
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
