"""Headcount card — demonstrates dash-bootstrap-components inside a cockpit card.

Uses dbc.Table and dbc.Badge. Shows that team cards can depend on dbc
independently of the cockpit shell (which uses dmc).
"""

import dash_bootstrap_components as dbc
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
    ("Engineering", 87, "primary"),
    ("Product",     24, "info"),
    ("Sales",       41, "success"),
    ("Finance",     12, "warning"),
    ("Operations",  18, "secondary"),
]


def render(context: dict):
    total = sum(n for _, n, _ in _DEPARTMENTS)
    rows = [
        html.Tr([
            html.Td(dept),
            html.Td(dbc.Badge(str(n), color=color, pill=True)),
        ])
        for dept, n, color in _DEPARTMENTS
    ]
    return html.Div([
        html.P(
            ["Total: ", dbc.Badge(str(total), color="dark", pill=True)],
            style={"fontWeight": "bold"},
        ),
        dbc.Table(
            [
                html.Thead(html.Tr([html.Th("Department"), html.Th("Count")])),
                html.Tbody(rows),
            ],
            bordered=True,
            hover=True,
            size="sm",
        ),
    ])


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


headcount_card = _Card()
