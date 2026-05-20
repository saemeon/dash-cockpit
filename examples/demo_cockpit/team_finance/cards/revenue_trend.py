"""Revenue trend card — demonstrates dmc inside a cockpit card.

Uses dash-mantine-components throughout: dmc.Table for the data grid,
dmc.Badge for the delta pill, dmc.Select in the settings slot.
The settings slot wires a "Comparison" dropdown that updates the headline
via a standard Dash callback — no cockpit-specific plumbing needed.
"""

import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, callback, html

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

_HEADLINE_ID = f"{CARD_META['id']}--headline"
_COMPARISON_ID = f"{CARD_META['id']}--comparison"


def _headline(comparison: str) -> tuple[str, str]:
    """Return (text, color) for the headline badge."""
    cy_total = sum(c for _, c, _ in _DATA)
    py_total = sum(p for _, _, p in _DATA)
    if comparison == "yoy":
        delta = (cy_total - py_total) / py_total * 100
        return f"${cy_total:.1f}M  ▲ {delta:.1f}% vs prior year", "green"
    if comparison == "target":
        target = py_total * 1.10
        pct = cy_total / target * 100
        return f"${cy_total:.1f}M  •  {pct:.0f}% of target", "blue"
    return f"${cy_total:.1f}M  absolute", "gray"


def render(context: dict):
    text, color = _headline("yoy")
    body = html.Div(
        [
            dmc.Badge(text, color=color, size="lg", mb="sm", id=_HEADLINE_ID),
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr([
                            dmc.TableTh("Month"),
                            dmc.TableTh("Current Year"),
                            dmc.TableTh("Prior Year"),
                        ])
                    ),
                    dmc.TableTbody([
                        dmc.TableTr([
                            dmc.TableTd(m),
                            dmc.TableTd(f"${cy}M"),
                            dmc.TableTd(f"${py}M"),
                        ])
                        for m, cy, py in _DATA
                    ]),
                ],
                striped=True,
                highlightOnHover=True,
                withTableBorder=True,
                fz="sm",
            ),
        ]
    )
    settings = html.Div(
        [
            dmc.Text("Comparison", fw=600, mb=4),
            dmc.Select(
                id=_COMPARISON_ID,
                data=[
                    {"label": "vs prior year", "value": "yoy"},
                    {"label": "vs target (10% growth)", "value": "target"},
                    {"label": "Absolute", "value": "abs"},
                ],
                value="yoy",
                allowDeselect=False,
            ),
            dmc.Text(
                "Choose the headline comparison. The badge refreshes automatically.",
                c="dimmed",
                fz="xs",
                mt="sm",
            ),
        ]
    )
    return {"body": body, "settings": settings}


@callback(
    Output(_HEADLINE_ID, "children"),
    Output(_HEADLINE_ID, "color"),
    Input(_COMPARISON_ID, "value"),
    prevent_initial_call=True,
)
def _update_headline(comparison: str):
    text, color = _headline(comparison or "yoy")
    return text, color


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
