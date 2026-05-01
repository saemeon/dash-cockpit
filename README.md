[![PyPI](https://img.shields.io/pypi/v/dash-cockpit)](https://pypi.org/project/dash-cockpit/)
[![Python](https://img.shields.io/pypi/pyversions/dash-cockpit)](https://pypi.org/project/dash-cockpit/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/badge/prek-checked-blue)](https://github.com/saemeon/prek)

# dash-cockpit

A **cards-first executive analytics cockpit** framework for Plotly Dash. Teams publish self-contained insight cards; the cockpit aggregates them into a single navigable dashboard with graceful failure isolation.

## Concept

```
Teams                    Cockpit
------                   -------
team_finance/            CardRegistry  ← get_cards() from each team
  cockpit_export/  ───►  Pages         ← compositions of card IDs
    cards/               CockpitApp    ← single Dash app
    export.py
```

The cockpit does **not** replace team applications — it is a read-oriented management abstraction layer on top of them.

## Installation

```bash
pip install dash-cockpit
```

## Quick start

```python
from dash_cockpit import CardRegistry, CockpitApp, TeamPage

# Build registry from installed team packages
registry = CardRegistry()
registry.load_packages(["team_finance", "team_ops"])

# Define pages as ordered card lists
pages = [
    TeamPage(name="Finance Overview", card_ids=["revenue_trend", "cash_position"], team="finance"),
    TeamPage(name="Operations", card_ids=["headcount", "ticket_volume"], team="ops"),
]

app = CockpitApp(registry=registry, pages=pages, title="Executive Cockpit")
app.run(debug=True)
```

## Writing a card

A card is any object with a `CARD_META` dict and a `render(context)` method:

```python
from dash import html

CARD_META = {
    "id": "revenue_trend",
    "title": "Revenue Trend",
    "team": "finance",
    "description": "Monthly revenue development",
    "refresh_interval": 300,
    "category": "finance",
}

def render(context: dict):
    # fetch your own data here
    return html.Div("$12.4M ▲ 3.2%")
```

## Team package contract

Each team package exposes a single `get_cards()` function:

```python
# team_finance/cockpit_export/export.py (re-exported from __init__)
from .cards.revenue import revenue_card
from .cards.cash_position import cash_position_card

def get_cards():
    return [revenue_card, cash_position_card]
```

## Failure isolation

If a card raises an exception, an error placeholder is rendered instead — the rest of the cockpit continues working:

```
┌──────────────────────────┐  ┌──────────────────────────┐
│  Revenue Trend           │  │  [broken_card] Error      │
│  $12.4M ▲ 3.2%           │  │  Connection refused       │
└──────────────────────────┘  └──────────────────────────┘
```

## User-defined pages

Users can compose their own page layouts as an explicit row grid:

```python
from dash_cockpit import UserPage

my_page = UserPage(
    name="My View",
    layout=[
        ["revenue_trend", "margin"],
        ["risk_exposure"],
    ],
)
```

## License

MIT
