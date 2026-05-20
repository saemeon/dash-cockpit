"""Cash position card — demonstrates dbc.Progress and dbc.Button inside a cockpit card.

Uses dash-bootstrap-components: dbc.Progress bars for utilisation,
dbc.Button for an "Export snapshot" action (stub — logs to console).
Shows that a dbc card sits comfortably next to dmc cards in the same cockpit.
"""

import dash_bootstrap_components as dbc
from dash import Input, Output, callback, html

CARD_META = {
    "id": "cash_position",
    "title": "Cash Position",
    "team": "finance",
    "description": "Current cash and liquidity summary",
    "refresh_interval": 600,
    "category": "finance",
    "size": (4, 4),
}

_ITEMS = [
    ("Cash & equivalents",    42.1, 80,  "success"),
    ("Short-term investments", 18.7, 35,  "info"),
    ("Credit facility (used)",  5.0, 10,  "danger"),
    ("Net position",           55.8, 100, "primary"),
]

_EXPORT_BTN_ID  = f"{CARD_META['id']}--export-btn"
_EXPORT_MSG_ID  = f"{CARD_META['id']}--export-msg"


def render(context: dict):
    rows = []
    for label, value, pct, color in _ITEMS:
        rows.append(html.Div([
            html.Div(
                [
                    html.Span(label, style={"fontSize": "0.85em"}),
                    html.Span(
                        f"${value:.1f}M",
                        style={"fontWeight": "bold", "marginLeft": "auto"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "marginBottom": "2px"},
            ),
            dbc.Progress(value=pct, color=color, style={"height": "6px"}, className="mb-2"),
        ]))

    return html.Div([
        html.P("As of today", style={"color": "#6c757d", "fontSize": "0.85em"}),
        html.Div(rows),
        dbc.Button(
            "Export snapshot",
            id=_EXPORT_BTN_ID,
            color="secondary",
            outline=True,
            size="sm",
            className="mt-2",
        ),
        html.Small(id=_EXPORT_MSG_ID, style={"marginLeft": "8px", "color": "#6c757d"}),
    ])


@callback(
    Output(_EXPORT_MSG_ID, "children"),
    Input(_EXPORT_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)
def _export(_):
    # Stub — in production this would trigger a download or notify an export backend.
    return "Snapshot queued."


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


cash_position_card = _Card()
