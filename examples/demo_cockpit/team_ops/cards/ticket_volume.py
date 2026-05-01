from dash import html

CARD_META = {
    "id": "ticket_volume",
    "title": "Support Ticket Volume",
    "team": "ops",
    "description": "Open and resolved support tickets this week",
    "refresh_interval": 120,
    "category": "operations",
}

_STATS = [
    ("Open", 34, "#dc3545"),
    ("In Progress", 18, "#ffc107"),
    ("Resolved this week", 91, "#198754"),
    ("Avg resolution (hrs)", "4.2", "#0d6efd"),
]


def render(context: dict):
    items = [
        html.Div(
            [
                html.Span(label, style={"color": "#6c757d"}),
                html.Span(
                    str(val),
                    style={"color": color, "fontWeight": "bold", "marginLeft": "auto"},
                ),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "padding": "4px 0",
                "borderBottom": "1px solid #f0f0f0",
            },
        )
        for label, val, color in _STATS
    ]
    return html.Div(
        [
            html.H5("Support Ticket Volume", style={"marginBottom": "8px"}),
            html.P("This week", style={"color": "#6c757d", "fontSize": "0.85em"}),
            html.Div(items),
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


ticket_volume_card = _Card()
