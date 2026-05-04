"""Per-card error isolation — a broken card must not break the page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dash import html

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._card import Card, RenderContext


def error_boundary(
    card: Card, context: RenderContext
) -> tuple[Component, Component | None, dict | None]:
    """Render a card and unwrap the slot dict, isolating errors.

    The cockpit's failure-isolation primitive plus slot-dict normaliser in
    one step. A bad card surfaces as a red placeholder tile (in the body
    slot) instead of crashing the page or its peers; settings and actions
    are left ``None`` for failed cards.

    Parameters
    ----------
    card : Card
        Any object satisfying the :class:`Card` protocol.
    context : RenderContext
        Render context forwarded to ``card.render``. See :class:`RenderContext`.

    Returns
    -------
    body : Component
        The card body — either the card's normal output (after slot-dict
        unwrap) or a red error tile.
    settings : Component or None
        Optional settings panel, or ``None`` if the card returned a bare
        Component / a dict without a ``settings`` slot / raised.
    actions : dict or None
        Optional render-time override of ``CARD_META["actions"]``, or ``None``
        in the same cases as ``settings``.
    """
    from dash_cockpit._card import unwrap_render_result

    try:
        result = card.render(context)
    except Exception as e:
        return _error_card(card.CARD_META["id"], str(e)), None, None
    return unwrap_render_result(result)


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
