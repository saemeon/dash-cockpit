"""Kennzahlen-style configurable card: pick a year, metric, and one or more divisions.

Multi-select on `division` fans out into one card per division (see `fanout_params`).
This mirrors the kennzahlenvergleich Shiny app: user assembles a custom report
from a small parameter grid, then exports it.
"""

from __future__ import annotations

import pandas as pd
from dash import html

from dash_cockpit import ParameterSpec, TemplateMeta

# Toy dataset — in production this would call team services.
_DATA = {
    (2024, "revenue", "EMEA"): 142.0,
    (2024, "revenue", "Americas"): 188.0,
    (2024, "revenue", "APAC"): 96.0,
    (2025, "revenue", "EMEA"): 158.0,
    (2025, "revenue", "Americas"): 211.0,
    (2025, "revenue", "APAC"): 110.0,
    (2024, "ebitda", "EMEA"): 24.0,
    (2024, "ebitda", "Americas"): 31.0,
    (2024, "ebitda", "APAC"): 12.0,
    (2025, "ebitda", "EMEA"): 30.0,
    (2025, "ebitda", "Americas"): 38.0,
    (2025, "ebitda", "APAC"): 15.0,
}


class _KpiCard:
    """Card produced by the template. Implements TabularCard for Excel/CSV export."""

    def __init__(self, year: int, metric: str, division: str):
        self._year = year
        self._metric = metric
        self._division = division
        self.CARD_META = {
            "id": "placeholder",  # overridden by the configurator
            "title": f"{metric.title()} {year} – {division}",
            "team": "finance",
            "description": f"{metric} for {division} in {year}",
            "refresh_interval": 0,
            "category": "finance",
        }

    def _value(self) -> float | None:
        return _DATA.get((self._year, self._metric, self._division))

    def _prior(self) -> float | None:
        return _DATA.get((self._year - 1, self._metric, self._division))

    def render(self, context: dict):
        v = self._value()
        py = self._prior()
        if v is None:
            body = html.P("No data", className="text-muted")
        else:
            delta_pct = ((v - py) / py * 100) if py else None
            colour = "#198754" if (delta_pct or 0) >= 0 else "#dc3545"
            delta = f"▲ {delta_pct:.1f}%" if delta_pct is not None else "—"
            body = html.Div(
                [
                    html.H3(f"${v:.0f}M"),
                    html.P(delta, style={"color": colour, "fontWeight": "bold"}),
                    html.Small(
                        f"prior year: ${py:.0f}M" if py else "no prior year",
                        className="text-muted",
                    ),
                ]
            )
        return html.Div(
            [
                html.H6(self.CARD_META["title"], style={"marginBottom": "8px"}),
                body,
            ],
            style={
                "padding": "16px",
                "background": "#fff",
                "border": "1px solid #dee2e6",
                "borderRadius": "6px",
            },
        )

    def get_tables(self) -> dict[str, pd.DataFrame]:
        v = self._value()
        py = self._prior()
        df = pd.DataFrame(
            [
                {
                    "year": self._year,
                    "metric": self._metric,
                    "division": self._division,
                    "value_musd": v,
                    "prior_value_musd": py,
                }
            ]
        )
        return {"kpi": df}


class _KpiLookupTemplate:
    TEMPLATE_META = TemplateMeta(
        id="kpi_lookup",
        title="KPI Lookup",
        team="finance",
        description="Pick a year, metric, and divisions",
        category="finance",
        parameters=[
            ParameterSpec(
                name="year",
                label="Year",
                type="select",
                options=[2024, 2025],
                default=2025,
            ),
            ParameterSpec(
                name="metric",
                label="Metric",
                type="select",
                options=["revenue", "ebitda"],
                default="revenue",
            ),
            ParameterSpec(
                name="division",
                label="Divisions",
                type="multi_select",
                options=["EMEA", "Americas", "APAC"],
                default=["EMEA"],
            ),
        ],
    )

    def instantiate(self, params: dict) -> _KpiCard:
        return _KpiCard(
            year=int(params["year"]),
            metric=str(params["metric"]),
            division=str(params["division"]),
        )


KpiLookupTemplate = _KpiLookupTemplate()
