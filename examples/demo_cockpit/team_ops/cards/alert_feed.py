"""Alert feed card — demonstrates dmc buttons with callbacks inside a cockpit card.

Each alert row has an "Acknowledge" button. Clicking it crosses the alert out
via a dcc.Store that tracks acknowledged IDs — no page reload, no cockpit
involvement. The card also has a "Clear all" button in the settings slot.

Demonstrates:
- dmc.Button with n_clicks callback (CARD_NO_DRAG_CLASS applied so the button
  doesn't accidentally drag the card)
- Per-card dcc.Store for local state
- Settings slot with a control that affects the body
"""

import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, callback_context, dcc, html

from dash_cockpit import CARD_NO_DRAG_CLASS

CARD_META = {
    "id": "alert_feed",
    "title": "Alert Feed",
    "team": "ops",
    "description": "Live operational alerts with acknowledge flow",
    "refresh_interval": 0,
    "category": "operations",
    "size": (4, 5),
}

_ALERTS = [
    {"id": "a1", "severity": "red",    "text": "API latency > 2s on /checkout"},
    {"id": "a2", "severity": "yellow", "text": "Disk usage at 81% on prod-db-02"},
    {"id": "a3", "severity": "yellow", "text": "Deploy queue stalled (15 min)"},
    {"id": "a4", "severity": "green",  "text": "Backup job completed successfully"},
    {"id": "a5", "severity": "red",    "text": "Payment gateway timeout (3 errors)"},
]

_STORE_ID   = f"{CARD_META['id']}--acked"
_LIST_ID    = f"{CARD_META['id']}--list"
_CLEAR_ID   = f"{CARD_META['id']}--clear"

_COLOR = {"red": "red", "yellow": "yellow", "green": "green"}
_LABEL = {"red": "Critical", "yellow": "Warning", "green": "OK"}


def _ack_btn_id(alert_id: str) -> dict:
    return {"type": f"{CARD_META['id']}--ack", "alert_id": alert_id}


def render(context: dict):
    body = html.Div([
        dcc.Store(id=_STORE_ID, data=[]),
        html.Div(id=_LIST_ID),
    ])
    settings = html.Div([
        dmc.Text("Alerts", fw=600, mb="xs"),
        dmc.Text(
            "Acknowledged alerts are crossed out until the card refreshes.",
            c="dimmed", fz="xs", mb="md",
        ),
        dmc.Button(
            "Clear all acknowledged",
            id=_CLEAR_ID,
            variant="light",
            color="gray",
            size="xs",
            className=CARD_NO_DRAG_CLASS,
            fullWidth=True,
        ),
    ])
    return {"body": body, "settings": settings}


@callback(
    Output(_LIST_ID, "children"),
    Input(_STORE_ID, "data"),
)
def _render_list(acked: list[str]):
    rows = []
    for alert in _ALERTS:
        aid = alert["id"]
        is_acked = aid in (acked or [])
        rows.append(
            dmc.Group(
                [
                    dmc.Badge(
                        _LABEL[alert["severity"]],
                        color=_COLOR[alert["severity"]],
                        size="xs",
                        w=70,
                    ),
                    dmc.Text(
                        alert["text"],
                        fz="sm",
                        td="line-through" if is_acked else "none",
                        c="dimmed" if is_acked else "inherit",
                        style={"flex": 1},
                    ),
                    dmc.Button(
                        "Ack" if not is_acked else "✓",
                        id=_ack_btn_id(aid),
                        size="xs",
                        variant="subtle" if not is_acked else "filled",
                        color="gray" if not is_acked else "green",
                        disabled=is_acked,
                        className=CARD_NO_DRAG_CLASS,
                    ),
                ],
                gap="xs",
                wrap="nowrap",
                py=4,
                style={"borderBottom": "1px solid var(--mantine-color-gray-2)"},
            )
        )
    return rows


@callback(
    Output(_STORE_ID, "data"),
    Input({"type": f"{CARD_META['id']}--ack", "alert_id": ALL}, "n_clicks"),
    State(_STORE_ID, "data"),
    prevent_initial_call=True,
)
def _acknowledge(n_clicks_list, acked):
    triggered = callback_context.triggered
    if not triggered:
        return acked or []
    import json
    prop_id = triggered[0]["prop_id"].rsplit(".", 1)[0]
    try:
        aid = json.loads(prop_id)["alert_id"]
    except (ValueError, KeyError):
        return acked or []
    current = list(acked or [])
    if aid not in current:
        current.append(aid)
    return current


@callback(
    Output(_STORE_ID, "data", allow_duplicate=True),
    Input(_CLEAR_ID, "n_clicks"),
    prevent_initial_call=True,
)
def _clear_acked(_):
    return []


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


alert_feed_card = _Card()
