# dash-cockpit: Configurator + Export Extensions

## Context

After studying `dash-reportbuilder/template-kennzahlenvergleich` (a working Shiny app that does exactly this workflow), we identified two missing pieces in dash-cockpit:

1. **Configurator** — a UI that lets end users *parametrize* an analysis card type and append concrete instances to a session-scoped page (the kennzahlen "Konfigurator" + "Bibliothek" tabs).
2. **Export** — a "download report" button that converts the current page (a list of cards) into PDF / Word / Excel via dash-reportbuilder.

## Honest naturalness assessment

| Extension | Naturalness | Verdict |
|---|---|---|
| **Export wiring** | High | Just do it. dash-reportbuilder's `REFACTOR_PLAN.md` already plans protocol-based element classes that expose optional facets (`TabularSource`, `ChartSource`, `DocumentRenderable`). Layering these protocols onto `Card` is a clean addition — concrete cards stay simple; cards that opt in get exportability for free. |
| **Configurator** | Medium | Worth doing, but expands scope. dash-cockpit's CLAUDE.md says "Cockpit owns presentation, not logic" and "Simplicity over runtime flexibility." A configurator turns cards into parametrizable factories — that straddles the presentation/logic boundary. Mitigated by making it strictly opt-in: cards remain atomic; *templates* are a separate, optional concept. |

Both fit the cockpit's cards-first model — the configurator just extends it from "static lists of cards" to "user-assembled lists of parametrized cards."

## Phase 1: Export wiring (implement now)

### New protocols (additive, all optional)

```python
# dash_cockpit/_export.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class TabularCard(Protocol):
    """Card that exposes tabular data for Excel/CSV export."""
    def get_tables(self) -> dict[str, "pd.DataFrame"]: ...

@runtime_checkable
class DocumentCard(Protocol):
    """Card that renders itself into a document backend (Word/PDF/HTML)."""
    def render_into_document(self, backend) -> None: ...

@runtime_checkable
class ChartCard(Protocol):
    """Card that exposes its chart as raw bytes (SVG/PNG)."""
    def get_chart(self, format: str) -> bytes: ...
    def chart_name(self) -> str: ...
```

Cards remain valid `Card`s without implementing these. A card can implement any subset.

### Page-level export

```python
def export_page(page: Page, registry: CardRegistry, backend) -> bytes:
    """Iterate page cards, dispatch each to the backend based on its protocols."""
```

dispatch rules:
- backend is **document-style** (Word/PDF/HTML) → look for `DocumentCard`; fall back to "card title + screenshot placeholder" for plain `Card`
- backend is **tabular** (Excel) → look for `TabularCard`; skip cards that don't implement it
- backend is **asset** (SVG/PNG zip) → look for `ChartCard`

### CockpitApp integration

Add a download button to the cockpit header. Click opens a modal with format radios (Word / PDF / Excel / SVG / PNG zip), validates against the current page's exportable cards, calls `export_page()`, serves via `dcc.Download`.

Modal pattern mirrors kennzahlenvergleich's `mod_export_modal`.

### dash-reportbuilder bridge

Don't import dash-reportbuilder hard. Use a thin protocol so the user passes any backend object that satisfies a tiny shape:

```python
@runtime_checkable
class ExportBackend(Protocol):
    def export(self, page_data: PageExportData) -> bytes: ...
```

Where `PageExportData` is a frozen dataclass that holds the page metadata + a list of `(card_meta, card_obj)` tuples. dash-reportbuilder backends can consume this; users can write their own.

This keeps dash-cockpit's only hard dep set unchanged.

## Phase 2: Configurator (implement next)

### CardTemplate protocol

A parametrizable card factory:

```python
@dataclass
class TemplateMeta:
    id: str
    title: str
    team: str
    description: str
    category: str
    parameters: list[ParameterSpec]  # see below

@runtime_checkable
class CardTemplate(Protocol):
    TEMPLATE_META: TemplateMeta
    def instantiate(self, params: dict) -> Card: ...
```

`ParameterSpec` describes one input field — name, label, type (`select`/`multi_select`/`number`/`date`), optional `options_fn(other_params) -> list` for cascading dropdowns (the kennzahlen pattern).

Templates are registered the same way as cards — teams add a `get_card_templates()` function alongside `get_cards()`. Both stay optional; teams can publish only static cards, only templates, or both.

### ConfiguratorPage

A new `Page` subtype:

```python
@dataclass
class ConfiguratorPage:
    name: str
    template_ids: list[str]      # which templates to expose
    initial_cards: list[str] = []
```

Renders as: left sidebar with template picker + parameter form; right pane with the user's working card list. Buttons:
- "Add" — instantiate the template with current params, append to working list, render
- "Remove" — drop card from list
- "Clear" — reset list
- "Export" — same export modal as Phase 1

The working list is held in a `dcc.Store` (session-scoped). The export action runs against that ad-hoc card list — no persistence in v1.

### Parameter form

Use `dash-fn-form` (already in the workspace). One form per template; parameter spec maps cleanly to dash-fn-form's field schema. Cascading options (e.g., year → metric → gender → level) handled via dash-fn-form's `options_fn` hooks.

### Registry additions

```python
class CardRegistry:
    def register_template(self, template: CardTemplate) -> None: ...
    def get_template(self, template_id: str) -> CardTemplate: ...
    def all_template_ids(self) -> list[str]: ...
    def load_packages(...):  # also calls get_card_templates() if present
```

## Phase 3 (later, optional)

- **Saved presets** (kennzahlen "Bibliothek") — JSON serialize a list of `(template_id, params)` tuples. File-store implementation; users can save/load named bundles.
- **Reorder / drag-drop** — kennzahlen has this code commented out; we'll punt the same way.
- **Per-card refresh / context propagation** — when the cockpit-level filter changes (e.g., date range), re-instantiate or refresh all cards. Needs a `refresh(context)` method on cards. Not in v1.

## File changes

```
dash-cockpit/
├── src/dash_cockpit/
│   ├── _export.py           # NEW — Phase 1 protocols + dispatch
│   ├── _template.py         # NEW — Phase 2 CardTemplate, TemplateMeta, ParameterSpec
│   ├── _configurator.py     # NEW — Phase 2 ConfiguratorPage rendering
│   ├── _registry.py         # ADD register_template, get_template, all_template_ids
│   ├── _page.py             # ADD ConfiguratorPage dataclass to Page union
│   ├── _layout.py           # ADD ConfiguratorPage branch
│   ├── _app.py              # ADD download button + export modal
│   └── __init__.py          # export new public names
├── tests/dash_cockpit/
│   ├── test_export.py       # NEW
│   ├── test_template.py     # NEW
│   └── test_configurator.py # NEW
└── examples/demo_cockpit/
    ├── team_finance/
    │   └── templates/       # NEW — at least one CardTemplate to demo cascading params
    └── app.py               # ADD a ConfiguratorPage
```

## Public API after both phases

```python
from dash_cockpit import (
    # Phase 0 (existing)
    Card, CardMeta, CardRegistry, CockpitApp, Page, TeamPage, UserPage,
    # Phase 1
    TabularCard, DocumentCard, ChartCard, ExportBackend, export_page,
    # Phase 2
    CardTemplate, TemplateMeta, ParameterSpec, ConfiguratorPage,
)
```

## Watch-outs (from kennzahlenvergleich)

- **Cascading dropdowns**: parameter B's options depend on parameter A's value. Need `options_fn(other_params)` in `ParameterSpec`.
- **Multi-select fanout**: kennzahlen "level" is multi-select → spawns one card per value. Make `instantiate()` callable per-value, not once.
- **Card identity**: each instantiated card needs a unique deterministic ID, e.g. `f"{template_id}-{hash(sorted(params.items()))}"`. Prevents duplicates in working list.
- **Slow instantiation**: kennzahlen shows a spinner if >4 cards; we use `dash`'s `loading_state` similarly.
- **Export validation**: disable PDF if a card with no `DocumentCard` impl is in the list (or render a placeholder); disable Excel if no `TabularCard` cards. Show why in modal.
- **No persistence in v1**: working list lives in `dcc.Store`. Saved presets come in Phase 3.

## Implementation order

1. Phase 1 protocols + dispatch + tests (no UI yet)
2. Phase 1 export modal + download button on `CockpitApp`
3. Phase 1 demo: add `TabularCard` impl to `revenue_trend`, wire export
4. Phase 2 `CardTemplate` + registry + tests
5. Phase 2 `ConfiguratorPage` rendering with dash-fn-form
6. Phase 2 demo: add a kennzahlen-style template to `team_finance`
