[![PyPI](https://img.shields.io/pypi/v/dash-cockpit)](https://pypi.org/project/dash-cockpit/)
[![Python](https://img.shields.io/pypi/pyversions/dash-cockpit)](https://pypi.org/project/dash-cockpit/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/badge/prek-checked-blue)](https://github.com/saemeon/prek)

# dash-cockpit

A **cards-first executive analytics cockpit** framework for Plotly Dash. Teams publish self-contained insight cards; the cockpit aggregates them into a single navigable dashboard with drag-and-drop layout, per-card menus, runtime composition, multi-format export, and graceful failure isolation.

## Mental model — iOS home screen for business insights

| iOS                | dash-cockpit          |
|--------------------|-----------------------|
| Widget             | **Card**              |
| Home screen        | **Page**              |
| OS shell           | **Cockpit (`CockpitApp`)** |
| App developer      | **Team package**      |

When in doubt: *"Would this make sense as an iPhone widget?"* If no, it doesn't belong in a card.

## Concept

```text
Teams                    Cockpit
------                   -------
team_finance/            CardRegistry  ← get_cards() / get_card_templates()
  cockpit_export/  ───►  Pages         ← compositions of cards
    cards/               CockpitApp    ← single Dash app
    templates/
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
    "size": (2, 1),  # optional: 2 columns wide, 1 row tall (in grid units)
}

def render(context: dict):
    # fetch your own data here
    return html.Div("$12.4M ▲ 3.2%", style={"height": "100%"})
```

Cards must fill their assigned grid cell — use `height: 100%` (or flex layout) on the outermost component, **never** fixed pixel heights. The cockpit guarantees the cell is exactly `row_height × h` pixels tall.

## Team package contract

Each team package exposes a single `get_cards()` (and optionally `get_card_templates()`) function:

```python
# team_finance/__init__.py
from .cards.revenue import revenue_card
from .cards.cash_position import cash_position_card
from .templates.kpi_lookup import kpi_template

def get_cards():
    return [revenue_card, cash_position_card]

def get_card_templates():
    return [kpi_template]
```

## Drag, resize, persist

Every `TeamPage` (and `ConfiguratorPage`) renders cards inside a draggable, resizable grid. Layout is persisted per browser to `localStorage` — refresh the page and the layout sticks. Card sizes default to `(1, 1)` and are read from each card's `CARD_META["size"]`.

The grid engine is [`dash-snap-grid`](https://github.com/idling-mind/dash_snap_grid); the cockpit pins it to one column-grid pattern but everything else is opaque.

### Edit mode

Cards are **locked by default** — view-only, no drag, no menus. Flip the **Edit layout** switch in the sidebar to enable drag, resize, and per-card menus. The state persists per browser (you stay in edit mode across reloads if you left it on).

This guards against executives accidentally rearranging their dashboard.

### Letting buttons inside cards work

Anything draggable swallows clicks on its children. If a card embeds a button, dropdown, or input, mark it with the `card-no-drag` class so the click goes through:

```python
from dash import html
from dash_cockpit import CARD_NO_DRAG_CLASS

def render(context):
    return html.Div([
        html.H3("Revenue"),
        html.Button("Refresh", className=CARD_NO_DRAG_CLASS),
    ], style={"height": "100%"})
```

Standard interactive HTML elements (`input`, `select`, `textarea`, `button`, `a`) are excluded from drag-start automatically. Use the class for non-standard wrappers (e.g. `dbc.DropdownMenu`, custom React components).

### Auto-refresh

A card declaring `refresh_interval > 0` (seconds) is auto-rerendered on a `dcc.Interval` tick. The cockpit handles wiring; cards just declare their cadence:

```python
CARD_META = {
    # ...required fields...
    "refresh_interval": 60,   # re-render every minute; 0 disables
}
```

A spinner is shown during slow re-renders.

## Per-card menus

Each card in the configurator renders a `⋮` dropdown for actions. Cards can opt into custom menu items by declaring `actions` in `CARD_META`:

```python
CARD_META = {
    # ...required fields...
    "actions": [
        {"id": "refresh", "label": "Refresh data"},
        {"id": "open_drill", "label": "Open drilldown"},
    ],
}
```

Action clicks emit pattern-matching callback events `{"type": "_cockpit_card_action", "card_id": ..., "action": ...}` — wire up handlers in your team package as needed.

## Failure isolation

If a card raises an exception, an error placeholder is rendered instead — the rest of the cockpit continues working:

```text
┌──────────────────────────┐  ┌──────────────────────────┐
│  Revenue Trend           │  │  [broken_card] Error     │
│  $12.4M ▲ 3.2%           │  │  Connection refused      │
└──────────────────────────┘  └──────────────────────────┘
```

## User-defined pages (preset layouts)

Compose static layouts as an explicit row grid. Useful for saved presets or "official" management views:

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

`UserPage` uses fixed Bootstrap rows (no drag-drop) — pick `TeamPage` if you want runtime drag-and-drop.

## Runtime composition (configurator pages)

Let users assemble pages on the fly from parametrised templates:

```python
from dash_cockpit import (
    CardTemplate,
    ConfiguratorPage,
    ParameterSpec,
    TemplateMeta,
)

class KPILookup:
    TEMPLATE_META = TemplateMeta(
        id="kpi_lookup",
        title="KPI lookup",
        team="finance",
        description="Pick a year and metric.",
        category="kennzahlen",
        parameters=[
            ParameterSpec(name="year", label="Year", type="select", options=[2024, 2025]),
            ParameterSpec(
                name="metric",
                label="Metric",
                type="multi_select",                    # fans out: one card per value
                options_fn=lambda p: METRICS[p.get("year")],  # cascading dropdown
            ),
        ],
    )

    def instantiate(self, params):
        # build and return a Card
        ...

# Register and add a configurator page
registry.register_template(KPILookup())
pages.append(ConfiguratorPage(name="KPI Builder", template_ids=["kpi_lookup"]))
```

`multi_select` parameters fan out: choosing 3 metrics produces 3 cards in the working list. Adding identical params twice is idempotent (deterministic id from `(template_id, params)`).

## Preset library

Configurator pages can load and save **presets** — named bundles of working-list entries, organised into freely-named **groups**. The framework prescribes no taxonomy: deployments invent their own group names (e.g. `"global"`, `"team:finance"`, `"user:alice"`). The store decides which groups the current viewer can see and write to.

Wire a `PresetStore` into the cockpit:

```python
from dash_cockpit import CockpitApp, LocalFilePresetStore, Preset

store = LocalFilePresetStore(
    "/var/cockpit/presets",
    seed=[
        Preset(
            name="Standard 2025",
            group="global",
            entries=[
                {"template_id": "kpi_lookup",
                 "params": {"year": 2025, "metric": "revenue"}},
            ],
        ),
    ],
)

app = CockpitApp(
    registry=registry,
    pages=pages,
    preset_store=store,
)
```

Each `ConfiguratorPage` shows a preset picker + Load/Save buttons. Picker labels include the group: `"global / Standard 2025"`, `"user:alice / My View"`. Saving with an existing `(group, name)` overwrites.

Bring your own backend by implementing the `PresetStore` protocol (`list_presets`, `save(preset)`, `load(group, name)`, `delete(group, name)`). `InMemoryPresetStore` is included for tests and demos.

### Group visibility & access control

`LocalFilePresetStore` decides which groups the current viewer sees and writes via three optional callables. The defaults read the current user from the `COCKPIT_USER` environment variable:

| Provider | Default behaviour | Returns |
|---|---|---|
| `visible_groups_provider` | `["global", f"user:{u}"]` if `$COCKPIT_USER`, else `["global"]` | groups shown in the picker |
| `writable_groups_provider` | `[f"user:{u}"]` if `$COCKPIT_USER`, else `[]` | groups the viewer can save to / delete from |
| `default_save_group_provider` | `f"user:{u}"` if `$COCKPIT_USER`, else `""` | group new user-saves go into |

For real auth, override any of them. Example with Flask:

```python
from flask import g
from dash_cockpit import LocalFilePresetStore, Preset

store = LocalFilePresetStore(
    "/var/cockpit/presets",
    seed=[Preset(name="Standard", group="global", entries=[...])],
    visible_groups_provider=lambda: ["global", "team:finance", f"user:{g.user_id}"],
    writable_groups_provider=lambda: [f"user:{g.user_id}"],
    default_save_group_provider=lambda: f"user:{g.user_id}",
)
```

Storage layout: `<directory>/<sanitised-group>/<sanitised-name>.json`. Group names are sanitised so user-controlled values can't escape the root via path traversal. Two users in different `user:*` groups never see or overwrite each other's presets. Seed presets are read-only — `save`/`delete` against a seeded `(group, name)` raises `PermissionError`.

The protocol itself stays neutral — group filtering is an implementation concern of the store, not the cockpit. The same pattern works for any backend (database, cloud, etc.).

## Export pipeline

Cards opt into export facets via runtime-checkable protocols:

```python
import pandas as pd

class RevenueCard:
    CARD_META = {...}

    def render(self, context):
        return html.Div(...)

    def get_tables(self) -> dict[str, pd.DataFrame]:
        # opt-in: TabularCard
        return {"revenue": self._df}
```

Wire export backends into the app:

```python
from my_export_backends import CSVZipBackend, WordBackend

app = CockpitApp(
    registry=registry,
    pages=pages,
    export_backends={
        "CSV (zip)": CSVZipBackend(),
        "Word":      WordBackend(),
    },
)
```

A "Download report" button appears in the sidebar; clicking it opens a format-radio modal. For `ConfiguratorPage`, the live working list is exported (not the static `initial_card_ids`).

Available protocols: `TabularCard`, `DocumentCard`, `ChartCard`. All opt-in; backends inspect each card with `isinstance` and decide what to do.

## License

MIT
