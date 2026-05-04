"""Cockpit-owned card chrome — the standard frame around every card body.

The cockpit is responsible for the *look* of a card (border, rounded corners,
header bar with title and … menu). Teams provide only the *body* — the actual
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


def _normalise_actions(
    actions: list[dict[str, Any]] | dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Coerce either the legacy or the render-time actions shape into one form.

    Two input shapes are accepted:

    - Legacy ``CARD_META["actions"]``: ``list[{"id": str, "label": str, ...}]``.
    - Render-time slot: ``dict[str, str | dict]`` where the value is either a
      label string (shorthand) or a dict carrying ``label`` plus extras.

    Both produce a uniform ``dict[id, {"label": str, ...extras}]`` with order
    preserved (insertion order in the input is kept).

    Parameters
    ----------
    actions : list, dict, or None
        Whichever shape the caller had on hand.

    Returns
    -------
    dict
        ``{action_id: {"label": str, ...}}``. Empty when ``actions`` is None
        or empty.
    """
    if not actions:
        return {}
    if isinstance(actions, list):
        out: dict[str, dict[str, Any]] = {}
        for entry in actions:
            aid = entry.get("id")
            if not aid:
                continue
            spec = {k: v for k, v in entry.items() if k != "id"}
            spec.setdefault("label", aid)
            out[aid] = spec
        return out
    # dict shape: value is str (label) or dict (label + extras).
    return {
        aid: ({"label": v} if isinstance(v, str) else {**v, "label": v.get("label", aid)})
        for aid, v in actions.items()
    }


STD_REFRESH = "_refresh"
STD_ABOUT = "_about"
STD_SETTINGS = "_settings"
"""Reserved IDs for cockpit-supplied standard actions.

Underscore-prefixed so collisions with team-defined IDs are obvious. Don't
use these for custom actions in ``CARD_META["actions"]`` or render-time
slot dicts — the cockpit auto-injects them and registers their callbacks.
"""

ABOUT_MODAL_ID = "_cockpit_about_modal"
ABOUT_MODAL_BODY_ID = "_cockpit_about_modal_body"
ABOUT_MODAL_TITLE_ID = "_cockpit_about_modal_title"

SETTINGS_DRAWER_ID = "_cockpit_settings_drawer"
SETTINGS_DRAWER_BODY_ID = "_cockpit_settings_drawer_body"


def build_about_modal() -> Component:
    """Build the empty app-level About modal added to :class:`CockpitApp`'s layout.

    The modal opens with content rendered server-side when any card's About
    … action fires. Add to your layout once at app construction; one modal
    serves every card.
    """
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("", id=ABOUT_MODAL_TITLE_ID),
                close_button=True,
            ),
            dbc.ModalBody(id=ABOUT_MODAL_BODY_ID),
        ],
        id=ABOUT_MODAL_ID,
        is_open=False,
    )


def register_about_callback(app, registry) -> None:
    """Wire the About … standard action to the app-level modal.

    One pattern-matching callback fires on every card's About click; the
    triggering ``card_id`` is parsed from ``callback_context``, the card's
    metadata fetched from the registry, and the modal populated with title
    + description + team.
    """
    from dash import ALL, Input, Output, callback_context, no_update

    @app.callback(
        Output(ABOUT_MODAL_ID, "is_open"),
        Output(ABOUT_MODAL_TITLE_ID, "children"),
        Output(ABOUT_MODAL_BODY_ID, "children"),
        Input(
            {
                "type": "_cockpit_card_action",
                "card_id": ALL,
                "action": STD_ABOUT,
            },
            "n_clicks",
        ),
        prevent_initial_call=True,
    )
    def _on_about(n_clicks_list):
        # No clicks anywhere yet (initial fan-out fires once with all-zeros).
        if not any(n_clicks_list or []):
            return no_update, no_update, no_update
        if not callback_context.triggered:
            return no_update, no_update, no_update
        import json as _json

        try:
            trigger_id = (
                callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0]
            )
            card_id = _json.loads(trigger_id).get("card_id")
        except (ValueError, KeyError, IndexError):
            return no_update, no_update, no_update
        try:
            entry = registry.get(card_id)
        except KeyError:
            return True, "Unknown card", html.Div(
                f"No card registered for id {card_id!r}."
            )
        meta = entry["meta"]
        body_children = [
            html.P(meta.get("description", ""), className="mb-2"),
            html.Div(
                [
                    html.Strong("Team: "),
                    html.Span(meta.get("team", "")),
                ],
                className="text-muted small",
            ),
        ]
        deep_link = meta.get("deep_link")
        if deep_link:
            body_children.append(
                html.Div(
                    html.A(
                        "Open in team app",
                        href=deep_link,
                        target="_blank",
                        rel="noopener",
                    ),
                    className="mt-2",
                )
            )
        return True, meta.get("title", card_id), html.Div(body_children)


def build_settings_drawer() -> Component:
    """Build the empty app-level settings drawer added to :class:`CockpitApp`'s layout.

    The drawer's body is populated server-side when any card's Settings …
    action fires; one drawer serves every card. The card's ``settings`` slot
    is re-rendered on each open, which keeps callback wiring simple (no
    duplicate IDs across body + settings copies).
    """
    return dbc.Offcanvas(
        html.Div(id=SETTINGS_DRAWER_BODY_ID),
        id=SETTINGS_DRAWER_ID,
        title="Settings",
        is_open=False,
        placement="end",
        backdrop=True,
    )


def register_settings_drawer_callback(app, registry, context_provider=None) -> None:
    """Open the side drawer with a card's settings slot when its Settings … fires.

    Re-calls ``card.render(context)`` on each open and extracts the
    ``settings`` slot via :func:`unwrap_render_result`. Re-rendering avoids
    duplicate-ID issues that would arise from rendering settings twice
    (once at card mount, once in the drawer) and keeps the slot's state
    fresh from the latest render context.

    Errors during settings re-render fall back to a small inline message
    in the drawer; the cockpit shell stays alive.
    """
    from dash import ALL, Input, Output, callback_context, no_update

    from dash_cockpit._card import unwrap_render_result

    @app.callback(
        Output(SETTINGS_DRAWER_ID, "is_open"),
        Output(SETTINGS_DRAWER_ID, "title"),
        Output(SETTINGS_DRAWER_BODY_ID, "children"),
        Input(
            {
                "type": "_cockpit_card_action",
                "card_id": ALL,
                "action": STD_SETTINGS,
            },
            "n_clicks",
        ),
        prevent_initial_call=True,
    )
    def _on_settings(n_clicks_list):
        if not any(n_clicks_list or []):
            return no_update, no_update, no_update
        if not callback_context.triggered:
            return no_update, no_update, no_update
        import json as _json

        try:
            trigger_id = (
                callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0]
            )
            card_id = _json.loads(trigger_id).get("card_id")
        except (ValueError, KeyError, IndexError):
            return no_update, no_update, no_update

        try:
            entry = registry.get(card_id)
        except KeyError:
            return True, "Settings", html.Div(
                f"No card registered for id {card_id!r}.",
                className="text-danger",
            )

        from dash_cockpit._layout import _CardShim

        card_obj = _CardShim(entry["render"], entry["meta"])
        ctx = context_provider() if context_provider is not None else {}
        try:
            result = card_obj.render(ctx)
        except Exception as e:  # noqa: BLE001 - surface in drawer, don't crash app
            return True, "Settings — error", html.Div(
                f"Error rendering settings: {e}",
                className="text-danger",
            )
        _body, settings, _actions = unwrap_render_result(result)
        if settings is None:
            # Card opted out of settings between page render and click — gracefully no-op.
            return True, "Settings", html.Div(
                "This card has no settings.",
                className="text-muted",
            )
        title = f"{entry['meta'].get('title', card_id)} — Settings"
        return True, title, settings


def card_chrome(
    body: Component,
    *,
    card_id: str,
    title: str = "",
    actions: list[dict[str, Any]] | dict[str, Any] | None = None,
    extra_menu_items: list[Component] | None = None,
    has_settings: bool = False,
) -> Component:
    """Wrap a card body in the standard cockpit chrome.

    The chrome supplies the border, rounded corners, header bar with title
    and … menu, and the body container that fills the remaining cell height.
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
    actions : list, dict, or None, optional
        Either the legacy ``CARD_META["actions"]`` list (``[{"id", "label"}, ...]``)
        or the render-time slot dict (``{action_id: str | {"label", ...extras}}``).
        See :func:`_normalise_actions`. By default ``None``.
    extra_menu_items : list[Component], optional
        Additional menu items appended after ``actions`` (e.g. a "Remove"
        item used by the configurator). By default ``None``.
    has_settings : bool, optional
        When ``True``, the cockpit auto-injects a "Settings" standard action
        that opens the side drawer with the card's settings slot. Set by
        :mod:`_layout` based on whether the card returned a ``settings`` slot.
        By default ``False``.

    Returns
    -------
    Component
        A self-contained card tile filling its grid cell.
    """

    def _action_item(aid: str, label: str, **extra: Any) -> Component:
        return dbc.DropdownMenuItem(
            label,
            id={
                "type": "_cockpit_card_action",
                "card_id": card_id,
                "action": aid,
            },
            n_clicks=0,
            **extra,
        )

    # 1. Custom actions (CARD_META["actions"] or render-time) come first.
    normalised = _normalise_actions(actions)
    custom_items: list[Component] = [
        _action_item(
            aid,
            spec.get("label", aid),
            href=spec.get("href"),
            disabled=spec.get("disabled", False),
            external_link=bool(spec.get("href")),
        )
        for aid, spec in normalised.items()
    ]

    # 2. Standard cockpit-supplied actions (always Refresh + About; Settings
    # only when the card returned a settings slot).
    standard_items: list[Component] = [
        _action_item(STD_REFRESH, "Refresh"),
        _action_item(STD_ABOUT, "About"),
    ]
    if has_settings:
        standard_items.append(_action_item(STD_SETTINGS, "Settings"))

    menu_items: list[Component] = list(custom_items)
    if custom_items:
        menu_items.append(dbc.DropdownMenuItem(divider=True))
    menu_items.extend(standard_items)
    if extra_menu_items:
        menu_items.append(dbc.DropdownMenuItem(divider=True))
        menu_items.extend(extra_menu_items)

    menu_block: Component
    if menu_items:
        menu_block = html.Div(
            dbc.DropdownMenu(
                label="…",
                children=menu_items,
                size="sm",
                color="link",
                align_end=True,
                caret=False,
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
