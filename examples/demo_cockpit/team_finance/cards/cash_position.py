from dash import html

CARD_META = {
    "id": "cash_position",
    "title": "Cash Position",
    "team": "finance",
    "description": "Current cash and liquidity summary",
    "refresh_interval": 600,
    "category": "finance",
}


def render(context: dict):
    items = [
        ("Cash & equivalents", "$42.1M", "positive"),
        ("Short-term investments", "$18.7M", "positive"),
        ("Credit facility (used)", "$5.0M", "negative"),
        ("Net position", "$55.8M", "positive"),
    ]
    rows = []
    for label, value, sentiment in items:
        color = "#198754" if sentiment == "positive" else "#dc3545"
        rows.append(
            html.Tr(
                [
                    html.Td(label),
                    html.Td(value, style={"color": color, "fontWeight": "bold"}),
                ]
            )
        )

    return html.Div(
        [
            html.H5("Cash Position", style={"marginBottom": "8px"}),
            html.P("As of today", style={"color": "#6c757d", "fontSize": "0.85em"}),
            html.Table(
                html.Tbody(rows),
                style={"width": "100%", "fontSize": "0.9em"},
            ),
        ],
        style={
            "padding": "16px",
            "background": "#fff",
            "border": "1px solid #dee2e6",
            "borderRadius": "6px",
        },
    )


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


cash_position_card = _Card()
