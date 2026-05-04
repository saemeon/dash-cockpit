"""Cockpit-owned card chrome — the standard frame around every card body.

The cockpit owns the card's *frame* (border, rounded corners, body padding)
and floats a `…` action menu in the top-right corner. The card body owns
everything else, including any title or heading the team wants to render.
There is **no chrome header bar**: a header eats vertical space and forces
visual uniformity teams don't always want; floating the menu over the body
keeps the full cell available for content (matches the cardcanvas approach).

The card protocol from a team's perspective:

    CARD_META = {"id": "...", "title": "...", ...}
    def render(context: dict) -> Component:
        # return the body. Render your own title inside if you want one.
        # The cockpit draws the border + the floating menu around it.
        ...

``CARD_META["title"]`` is still consumed elsewhere (the About modal, the
registry, the navigation breadcrumbs); it's just no longer displayed by the
chrome.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import dash_mantine_components as dmc
from dash import html

from dash_cockpit._packing import CARD_MENU_CLASS

if TYPE_CHECKING:
    from dash.development.base_component import Component


_CARD_STYLE = {
    # position: relative anchors the floating menu's absolute positioning.
    "position": "relative",
    "height": "100%",
    "background": "#ffffff",
    "border": "1px solid #dee2e6",
    "borderRadius": "8px",
    "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.04)",
    "overflow": "hidden",
}

_BODY_STYLE = {
    "height": "100%",
    "padding": "12px",
    "overflow": "auto",
}

_MENU_OVERLAY_STYLE = {
    # Float the … menu top-right so the chrome owns no visible header bar.
    # Cards control their own visual including any title they want.
    "position": "absolute",
    "top": "4px",
    "right": "4px",
    "zIndex": 2,
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

SETTINGS_DRAWER_ID = "_cockpit_settings_drawer"
SETTINGS_DRAWER_BODY_ID = "_cockpit_settings_drawer_body"


def build_about_modal() -> Component:
    """Build the empty app-level About modal added to :class:`CockpitApp`'s layout.

    The modal opens with content rendered server-side when any card's About
    … action fires. Add to your layout once at app construction; one modal
    serves every card. ``title`` is set by the open-callback via
    ``Output(ABOUT_MODAL_ID, "title")``.
    """
    return dmc.Modal(
        children=html.Div(id=ABOUT_MODAL_BODY_ID),
        id=ABOUT_MODAL_ID,
        title="",
        opened=False,
        centered=True,
        size="md",
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
        Output(ABOUT_MODAL_ID, "opened"),
        Output(ABOUT_MODAL_ID, "title"),
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
    return dmc.Drawer(
        children=html.Div(id=SETTINGS_DRAWER_BODY_ID),
        id=SETTINGS_DRAWER_ID,
        title="Settings",
        opened=False,
        position="right",
        size="md",
        # Mantine's drawer uses an overlay (backdrop) by default; explicit for clarity.
        overlayProps={"backgroundOpacity": 0.4, "blur": 1},
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
        Output(SETTINGS_DRAWER_ID, "opened"),
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

    The chrome supplies the border, rounded corners, body padding, and a
    floating `…` action menu in the top-right corner. There is no header
    bar — cards render their own title (if they want one) inside the body.

    Parameters
    ----------
    body : Component
        The team-provided card body. May render anything Dash supports;
        will be placed inside a scrollable body container that fills the
        whole cell.
    card_id : str
        ``CARD_META["id"]``. Used for action callback ids.
    title : str, optional
        Accepted for API compatibility and used by the About modal lookup
        elsewhere — **not rendered by the chrome**. Cards that want a
        visible title draw it inside their body.
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
        # Map our extras to dmc.MenuItem props. dmc uses href + target like
        # an anchor; disabled is identical.
        kwargs: dict[str, Any] = {}
        if extra.get("href"):
            kwargs["href"] = extra["href"]
            # Open external links in a new tab — matches dbc's external_link.
            kwargs["target"] = "_blank"
        if extra.get("disabled"):
            kwargs["disabled"] = True
        return dmc.MenuItem(
            label,
            id={
                "type": "_cockpit_card_action",
                "card_id": card_id,
                "action": aid,
            },
            n_clicks=0,
            **kwargs,
        )

    # 1. Custom actions (CARD_META["actions"] or render-time) come first.
    normalised = _normalise_actions(actions)
    custom_items: list[Component] = [
        _action_item(
            aid,
            spec.get("label", aid),
            href=spec.get("href"),
            disabled=spec.get("disabled", False),
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
        menu_items.append(dmc.MenuDivider())
    menu_items.extend(standard_items)
    if extra_menu_items:
        menu_items.append(dmc.MenuDivider())
        menu_items.extend(extra_menu_items)

    children: list[Component] = [html.Div(body, style=_BODY_STYLE)]
    if menu_items:
        children.append(
            html.Div(
                dmc.Menu(
                    [
                        dmc.MenuTarget(
                            dmc.ActionIcon(
                                "…",
                                variant="subtle",
                                color="gray",
                                size="sm",
                                radius="xl",
                                # Ensure clicks here don't trigger drag-start.
                                className=CARD_MENU_CLASS,
                                **{"aria-label": "Card menu"},
                            ),
                        ),
                        dmc.MenuDropdown(menu_items),
                    ],
                    position="bottom-end",
                    shadow="md",
                    width=200,
                ),
                style=_MENU_OVERLAY_STYLE,
            )
        )

    return html.Div(
        children,
        style=_CARD_STYLE,
        className="cockpit-card",
    )
