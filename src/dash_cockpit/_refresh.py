"""Per-card auto-refresh — wires ``CARD_META["refresh_interval"]`` to a Dash callback.

A card whose metadata declares ``refresh_interval > 0`` is wrapped in a
:class:`dcc.Interval` plus a body :class:`html.Div` with a pattern-matching
id. One server-side callback (registered by :func:`register_refresh_callbacks`)
re-renders the card body each time the interval fires.

Cards with ``refresh_interval == 0`` (the default) are wrapped without an
Interval, so the callback never fires for them — zero overhead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dash import dcc, html

from dash_cockpit._error import error_boundary

if TYPE_CHECKING:
    from dash.development.base_component import Component

    from dash_cockpit._registry import CardRegistry


CARD_BODY_ID_TYPE = "_cockpit_card_body"
"""``type`` field of every refreshable card body's pattern-matching id."""

CARD_INTERVAL_ID_TYPE = "_cockpit_card_interval"
"""``type`` field of every refresh :class:`dcc.Interval`'s pattern-matching id."""


def card_body_id(card_id: str) -> dict[str, str]:
    """Build the pattern-matching id for a card body wrapper.

    Parameters
    ----------
    card_id : str
        The card's ``CARD_META["id"]``.

    Returns
    -------
    dict
        Pattern-matching id of the form
        ``{"type": _cockpit_card_body, "card_id": card_id}``.
    """
    return {"type": CARD_BODY_ID_TYPE, "card_id": card_id}


def card_interval_id(card_id: str) -> dict[str, str]:
    """Build the pattern-matching id for a card refresh :class:`dcc.Interval`.

    Parameters
    ----------
    card_id : str
        The card's ``CARD_META["id"]``.

    Returns
    -------
    dict
        Pattern-matching id of the form
        ``{"type": _cockpit_card_interval, "card_id": card_id}``.
    """
    return {"type": CARD_INTERVAL_ID_TYPE, "card_id": card_id}


def wrap_for_refresh(
    component: Component, card_id: str, refresh_interval: int
) -> Component:
    """Wrap a card component so its body is targetable and (optionally) refreshable.

    Parameters
    ----------
    component : Component
        The card's rendered component.
    card_id : str
        The card's ``CARD_META["id"]``.
    refresh_interval : int
        Refresh cadence in seconds. ``0`` skips the :class:`dcc.Interval` —
        the wrapper still has a stable body id but no callback ever fires.

    Returns
    -------
    Component
        A :class:`html.Div` wrapper. If ``refresh_interval > 0``, includes a
        sibling :class:`dcc.Interval`.
    """
    # Wrap in dcc.Loading so slow re-renders show a spinner instead of
    # appearing frozen. The loading overlay is transparent until the
    # update actually takes time, so there's no visual cost on fast renders.
    body = html.Div(
        dcc.Loading(
            component,
            type="default",
            parent_style={"height": "100%", "width": "100%"},
            overlay_style={"visibility": "visible"},
        ),
        id=card_body_id(card_id),
        style={"height": "100%", "width": "100%"},
    )
    if refresh_interval and refresh_interval > 0:
        return html.Div(
            [
                dcc.Interval(
                    id=card_interval_id(card_id),
                    interval=int(refresh_interval) * 1000,  # ms
                    n_intervals=0,
                ),
                body,
            ],
            style={"height": "100%", "width": "100%"},
        )
    return body


def register_refresh_callbacks(
    app,
    registry: CardRegistry,
    context_provider=None,
) -> None:
    """Register the pattern-matching callback that re-renders cards on tick.

    One callback handles every refreshable card via ``MATCH`` on the
    ``card_id`` field. Each interval fires only for its own card; the
    callback looks the card up in the registry, calls
    :func:`error_boundary` on it, and returns the new body component.

    Parameters
    ----------
    app : dash.Dash
        The Dash app to register the callback on.
    registry : CardRegistry
        Registry used to resolve card IDs at callback time.

    Notes
    -----
    Errors in the card's render are caught by :func:`error_boundary` and
    surface as the standard red placeholder tile, matching the failure-
    isolation behaviour of the initial render path.
    """
    from dash import MATCH, Input, Output

    @app.callback(
        Output(card_body_id(MATCH), "children"),
        Input(card_interval_id(MATCH), "n_intervals"),
        prevent_initial_call=True,
    )
    def _refresh_card(_n_intervals):
        # Pattern-matching gives us the matched card_id via callback context.
        from dash import callback_context

        ctx = callback_context
        if not ctx.triggered:
            return html.Div("(no trigger)")
        # Trigger prop_id looks like '{"card_id":"foo","type":"_cockpit_card_interval"}.n_intervals'
        import json as _json

        try:
            trigger_id = ctx.triggered[0]["prop_id"].rsplit(".", 1)[0]
            payload = _json.loads(trigger_id)
            card_id = payload.get("card_id")
        except (ValueError, KeyError, IndexError):
            return html.Div("(invalid trigger)")
        try:
            entry = registry.get(card_id)
        except KeyError:
            return html.Div(f"Unknown card: {card_id!r}")

        from dash_cockpit._layout import _CardShim

        card_obj = _CardShim(entry["render"], entry["meta"])
        ctx = context_provider() if context_provider is not None else {}
        return error_boundary(card_obj, ctx)
