from dash import html

CARD_META = {
    "id": "headcount",
    "title": "Headcount",
    "team": "ops",
    "description": "Active headcount by department",
    "refresh_interval": 0,
    "category": "people",
    "size": (3, 5),
}

_DEPARTMENTS = [
    ("Engineering", 87),
    ("Product", 24),
    ("Sales", 41),
    ("Finance", 12),
    ("Operations", 18),
]


def render(context: dict):
    total = sum(n for _, n in _DEPARTMENTS)
    rows = [html.Tr([html.Td(dept), html.Td(str(n))]) for dept, n in _DEPARTMENTS]
    return html.Div(
        [
            html.P(f"Total: {total} employees", style={"fontWeight": "bold"}),
            html.Table(
                [
                    html.Thead(html.Tr([html.Th("Department"), html.Th("Count")])),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "fontSize": "0.9em"},
            ),
        ]
    )


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


headcount_card = _Card()
