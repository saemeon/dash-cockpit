import pandas as pd
from dash import html

CARD_META = {
    "id": "revenue_trend",
    "title": "Revenue Trend",
    "team": "finance",
    "description": "Monthly revenue development vs. prior year",
    "refresh_interval": 300,
    "category": "finance",
}

_DATA = [
    ("Jan", 9.1, 8.4),
    ("Feb", 9.8, 8.9),
    ("Mar", 10.4, 9.7),
    ("Apr", 12.4, 10.1),
]


def render(context: dict):
    rows = [
        html.Tr([html.Td(m), html.Td(f"${cy}M"), html.Td(f"${py}M")])
        for m, cy, py in _DATA
    ]
    return html.Div(
        [
            html.H5("Revenue Trend", style={"marginBottom": "8px"}),
            html.P("$12.4M ▲ 22.8% vs prior year", style={"color": "#198754", "fontWeight": "bold"}),
            html.Table(
                [
                    html.Thead(html.Tr([html.Th("Month"), html.Th("Current Year"), html.Th("Prior Year")])),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "fontSize": "0.9em"},
            ),
        ],
        style={"padding": "16px", "background": "#fff", "border": "1px solid #dee2e6", "borderRadius": "6px"},
    )


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)

    def get_tables(self) -> dict[str, pd.DataFrame]:
        df = pd.DataFrame(_DATA, columns=["month", "current_year_musd", "prior_year_musd"])
        return {"revenue_trend": df}


revenue_trend_card = _Card()
