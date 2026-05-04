"""Revenue trend card — demonstrates the settings slot.

Returns a slot dict ``{"body": ..., "settings": ...}``. The settings
panel holds a "Comparison" dropdown; changing it updates the body's
headline. State is shared via a per-card ``dcc.Store`` and one
top-level Dash callback registered at module load time.
"""

from dash import Input, Output, callback, dcc, html

import pandas as pd

CARD_META = {
    "id": "revenue_trend",
    "title": "Revenue Trend",
    "team": "finance",
    "description": "Monthly revenue development vs. prior year",
    "refresh_interval": 300,
    "category": "finance",
    "size": (8, 4),
    "deep_link": "https://example.com/finance/revenue",
}

_DATA = [
    ("Jan", 9.1, 8.4),
    ("Feb", 9.8, 8.9),
    ("Mar", 10.4, 9.7),
    ("Apr", 12.4, 10.1),
]

# Per-card component IDs. Stable strings derived from CARD_META["id"] so
# the body and settings can find each other via callbacks.
_HEADLINE_ID = f"{CARD_META['id']}--headline"
_COMPARISON_ID = f"{CARD_META['id']}--comparison"


def _headline(comparison: str) -> str:
    cy_total = sum(c for _, c, _ in _DATA)
    py_total = sum(p for _, _, p in _DATA)
    if comparison == "yoy":
        delta = (cy_total - py_total) / py_total * 100
        return f"${cy_total:.1f}M  ▲ {delta:.1f}% vs prior year"
    if comparison == "target":
        target = py_total * 1.10  # 10% growth target
        pct = cy_total / target * 100
        return f"${cy_total:.1f}M  •  {pct:.0f}% of target"
    return f"${cy_total:.1f}M  absolute"


def render(context: dict):
    rows = [
        html.Tr([html.Td(m), html.Td(f"${cy}M"), html.Td(f"${py}M")])
        for m, cy, py in _DATA
    ]
    body = html.Div(
        [
            html.P(
                _headline("yoy"),
                id=_HEADLINE_ID,
                style={"color": "#198754", "fontWeight": "bold"},
            ),
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Month"),
                                html.Th("Current Year"),
                                html.Th("Prior Year"),
                            ]
                        )
                    ),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "fontSize": "0.9em"},
            ),
        ]
    )
    settings = html.Div(
        [
            html.Label("Comparison", style={"fontWeight": "600"}),
            dcc.Dropdown(
                id=_COMPARISON_ID,
                options=[
                    {"label": "vs prior year", "value": "yoy"},
                    {"label": "vs target (10% growth)", "value": "target"},
                    {"label": "Absolute", "value": "abs"},
                ],
                value="yoy",
                clearable=False,
                style={"marginTop": "4px"},
            ),
            html.P(
                "Choose the headline comparison. The card body refreshes "
                "automatically when this changes.",
                className="text-muted small mt-3",
            ),
        ]
    )
    return {"body": body, "settings": settings}


@callback(
    Output(_HEADLINE_ID, "children"),
    Input(_COMPARISON_ID, "value"),
    prevent_initial_call=True,
)
def _update_headline(comparison: str) -> str:
    return _headline(comparison or "yoy")


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)

    def get_tables(self) -> dict[str, pd.DataFrame]:
        df = pd.DataFrame(
            _DATA, columns=["month", "current_year_musd", "prior_year_musd"]
        )
        return {"revenue_trend": df}


revenue_trend_card = _Card()
