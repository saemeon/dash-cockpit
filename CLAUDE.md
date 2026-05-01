# dash-cockpit

> Read this section first. The full blueprint below is the deeper reference.

## Mental model: an "iOS home screen for business insights"

The cockpit is structurally an iOS-style widget shell.

| iOS                | dash-cockpit          |
|--------------------|-----------------------|
| Widget             | **Card**              |
| Home screen        | **Page**              |
| OS shell           | **Cockpit (CockpitApp)** |
| App developer      | **Team package**      |

What this analogy gets you — for free:
- **Cards must be independent.** No cross-card state. (Like widgets.)
- **Cards are small and focused.** If it's bigger than a widget, it's a dashboard, not a card.
- **Cockpit owns layout, not logic.** Cards never decide their own placement.
- **Graceful degradation.** One broken card must not break the page (like a crashed widget on iOS).

When in doubt: *"Would this make sense as an iPhone widget?"* If no, it doesn't belong in a card.

## The whole system in three lines

1. **Cards** — atomic units of insight. Teams ship a set per domain.
2. **Lists of cards** — the only kind of page there is. Three sources:
   - **Predefined** by a team (e.g. "Finance Overview"): a curated card list.
   - **Predefined** by anyone, with no dedicated tab: a saved bundle the user can load.
   - **User-built** via a configurator: a card list the user assembles at runtime from any registered card or template.
3. **Cockpit** — the shell that loads packages, owns layout, and renders the active page's card list.

Everything else (export, configurator, `TabularCard` / `DocumentCard` protocols, `CardTemplate`, multi-select fanout) is plumbing in service of those three concepts.

## Third-party tools: decisions made

### CardCanvas (`../cardcanvas/`)

CardCanvas (vendored in this workspace) is a **Dash layout/composition engine** — drag-drop grid, per-card menus, settings drawers, share-by-URL. It is well-built for that narrow problem.

**Decision: do not adopt CardCanvas as our foundation.**

Reasons:
- It solves ~20% of our problem (UI layout). The other 80% — multi-team packages, `get_cards()` contract, governance/validation at startup, failure isolation, export protocols, templates — we still build ourselves.
- Its `Card` ABC assumes everything lives in one app; our cards fetch from distributed team backends.
- Adopting it means bending our architecture to fit its assumptions (single canvas, no pages, no team dispatch).

**Decision: adopt `dash-snap-grid` later, as a layout-layer swap.**

`dash-snap-grid` (`ResponsiveGrid`) is the drag-drop grid engine CardCanvas uses internally. It is a pure UI primitive with no opinions about cards, data, or team ownership. When we need drag-drop layout:
- Replace `dbc.Row`/`dbc.Col` packing in `_layout.py` with `ResponsiveGrid`.
- Store layout as `dcc.Store(storage_type="local")` per page — free persistence.
- Card's `size` field becomes the default `{w, h}` hint before the user manually drags.

This is a ~50-line change in `_layout.py`. No other module needs to change. Do this in Phase 3.

---

## Future direction: widget sizing

Pages are currently uniform grids (`columns=N`, every card same width). The next natural extension — and the one the iOS analogy suggests — is **cards declaring a size hint** in widget units:

- A page is an N-column grid (e.g. N=4).
- A card declares `size=(width_units, height_units)` in `CARD_META`, e.g. `(1,1)` small, `(2,1)` medium, `(2,2)` large, `(4,1)` banner.
- The cockpit lays out cards in declaration order, wrapping to a new row when a card doesn't fit.
- Default `(1,1)` keeps existing cards working unchanged.

Not implemented yet. The hooks to add later: a `size` field on `CardMeta`, a packing function in `_layout.py`, and a `grid_columns` field on `Page`.

## Implementation status (as of writing)

- **Phase 1 — Export wiring:** ✅ shipped.
  - Protocols: `TabularCard`, `DocumentCard`, `ChartCard`, `ExportBackend`. All `runtime_checkable`, all opt-in.
  - `export_page(page, registry, backend) -> bytes`; backends consume `PageExportData` (frozen dataclass).
  - `CockpitApp(export_backends={"label": backend})` adds a download button + format-radio modal.
  - Demo: `revenue_trend` is a `TabularCard`; `examples/demo_cockpit/csv_zip_backend.py` exports any `TabularCard` page as a zip of CSVs.
- **Phase 2 — Configurator:** ✅ shipped (v1).
  - `CardTemplate` protocol with `TemplateMeta` and `ParameterSpec` (types: `select`, `multi_select`, `number`, `date`, `text`).
  - `card_id_for(template_id, params)` — deterministic, order-insensitive id; idempotent Add.
  - `fanout_params` — multi-select expands cartesian-product into one card per scalar value (kennzahlen pattern).
  - `ConfiguratorPage` is in the `Page` union; `_layout.render_page` dispatches to it.
  - `_configurator.py` provides server-side rendering + Dash callbacks (template picker → form swap → store mutation → cards-pane re-render). State lives in a session `dcc.Store`.
  - Per-card actions surface via a `⋮` dropdown menu (top-right of each tile).
  - Export modal is configurator-aware: when on a `ConfiguratorPage`, it exports the live working list, not the page's static `card_ids`.
  - Demo: `team_finance/templates/kpi_lookup.py` ships a kennzahlen-style template (year × metric × multi-division).
- **Phase 3 (later, optional):** saved presets ("Bibliothek"), drag-drop reorder, per-card refresh/context propagation, widget sizing.

## Known limitations / honest caveats

- **`ParameterSpec.options_fn` is accepted but ignored.** Cascading dropdowns are documented as a feature on the dataclass but not yet wired through `_field_component`. Either implement or remove.
- **The form is bespoke, not dash-fn-form.** Originally planned to use `dash-fn-form` (already in the workspace) for parameter rendering; v1 uses dbc/dcc directly. Revisit before scope grows.
- **Configurator callbacks are not test-covered.** Pure helpers are; the live pattern-matching callback bodies require a running Dash app and have only been smoke-tested.
- **No export-format validation.** Backend that sees a page with no compatible cards is responsible for handling it (the demo writes a `README.txt`). A more opinionated cockpit would gray out incompatible formats in the modal.
- **Cards can't yet declare a size.** Layout is uniform-grid only.

---

Team Cockpit System Blueprint (Cards-first executive layer)
1. Purpose and scope
You are building an executive cockpit on top of an ecosystem of existing internal team applications.
It is important to restate the separation clearly:
Team applications (existing, unchanged)
* Full internal tools per domain (Finance, Ops, Product, etc.)
* Contain workflows, editing, deep analysis, operational tooling
* Are not constrained by cockpit design
* Own their own data access and business logic
Cockpit (new system)
* Executive-facing overview layer
* Read-oriented, signal-driven
* Built on a single Plotly Dash application
* Aggregates “cards” from all teams
* Provides structured pages (predefined or user-defined)
The cockpit does NOT replace team apps. It is a management abstraction layer.

1. Core architectural decision: cards-first system
You decided correctly to move to a cards-first model.
2.1 What a card is
A card is the atomic unit of insight exposed by a team for management consumption.
It is:
* a self-contained rendering function
* optionally interactive (light interactions only)
* responsible for its own data retrieval
* visually consistent via shared conventions
Cards are NOT:
* full dashboards
* workflows
* multi-component applications

2.2 Card contract (mandatory interface)
Each card must implement:
def render(context: dict):
    """
    Must return a Dash component.
    Must be fully self-contained.
    """
Cards may internally:
* fetch data from their own team systems
* call internal services
* perform lightweight aggregation
But:
* they must NOT depend on other cards
* they must NOT assume global state

2.3 Card metadata
Each card also exposes metadata:
CARD_META = {
    "id": "revenue_trend",
    "title": "Revenue Trend",
    "team": "finance",
    "description": "Monthly revenue development",
    "refresh_interval": 300,
    "category": "finance"
}
This enables:
* global registry
* search/filtering
* layout composition

3. Team integration model
Each team delivers a Python package per domain, installed into the cockpit runtime environment (via controlled environment such as a Posit-managed environment or similar).
No runtime Git loading. Everything is installed at startup.

3.1 Team repository structure
Each team repo contains:
team_finance/
│
├── internal_app/
│   ├── workflows/
│   ├── services/
│   └── dashboards/
│
├── cockpit_export/
│   ├── cards/
│   │   ├── revenue.py
│   │   ├── cash_position.py
│   │
│   └── export.py
│
└── pyproject.toml

3.2 Export contract (critical boundary)
Each team exposes:
def get_cards():
    return [
        revenue_card,
        cash_position_card
    ]
This is the ONLY interface the cockpit consumes.

3.3 Key principle
* internal_app = full operational system
* cockpit_export = management abstraction layer
This avoids coupling operational logic to executive views.

4. Cockpit system design
4.1 Startup model (important decision)
All packages are loaded at startup.
* No runtime plugin installation
* No dynamic Git loading
* Updates require redeployment
This ensures stability.

4.2 Card registry
At startup:
1. import all team packages
2. call get_cards()
3. build global registry
Structure:
CARD_REGISTRY = {
    "revenue_trend": {
        "render": <function>,
        "meta": {...}
    }
}

4.3 Failure model (critical requirement)
Cards are isolated units.
If a card fails:
* it must NOT break the cockpit
* it must render an error placeholder
* system continues functioning
Example pattern:
try:
    output = card.render(context)
except Exception as e:
    output = ErrorCard(card_id, str(e))
This ensures graceful degradation.

5. Page system (important clarification from your design)
You defined a unified abstraction: pages are compositions of cards.
This is correct and central.

5.1 Two page types
A. Team-defined pages (curated views)
* predefined arrangement of cards
* stable structure
* used for “official” management views
PAGE = {
    "name": "Finance Overview",
    "cards": [
        "revenue_trend",
        "cash_position",
        "margin"
    ]
}

B. User-defined pages (dynamic layouts)
* users assemble cards themselves
* layout is stored as configuration
USER_PAGE = {
    "layout": [
        ["revenue_trend", "margin"],
        ["risk_exposure"]
    ]
}

5.2 Key abstraction
You explicitly unified the system:
A page is just a list (or grid) of cards.
This is the core simplification that enables:
* consistency
* reuse
* future extensibility (Bloomberg-style layouts)

6. Layout system
Initial version:
* simple grid (rows/columns)
* fixed rendering
* no drag-and-drop yet
Later extension (optional):
* user-configurable layout engine
* persistence of layouts
But not needed for MVP.

7. Cockpit runtime flow
7.1 Startup
1. load all installed team packages
2. call get_cards() for each team
3. build global CARD_REGISTRY
4. validate:
    * duplicate card IDs
    * missing metadata
    * broken imports

7.2 Rendering flow
1. user selects page
2. cockpit resolves list of card IDs
3. for each card:
    * call render(context)
    * wrap in error boundary
4. compose into grid layout
5. display in Dash UI

8. Data ownership model (important constraint)
You explicitly chose:
* each team fetches its own data
* cockpit does NOT mediate data access
Implications:
* cards are responsible for correctness of their own data
* potential inconsistency risk is accepted for autonomy
* no central data abstraction layer required initially
This keeps system flexible but requires discipline.

9. Interaction model
Allowed:
* light interactions inside cards
* filtering within a card
* hover/selection states
* small drilldowns
Not allowed (initially):
* cross-card interactions
* global state dependencies between cards

10. Versioning strategy
You chose strict versioning:
* dependencies pinned in environment (requirements-based)
* no runtime version switching
* updates happen via redeploy
This matches your controlled deployment environment.

11. Failure strategy (non-negotiable)
System must:
* continue rendering if individual cards fail
* display error card instead of breaking UI
* isolate failures per card only
This is critical for executive reliability.

12. Package distribution model
All team packages:
* installed into shared environment
* managed centrally
* loaded at startup
You are NOT using:
* Git-based runtime loading
* dynamic plugin fetching
You ARE using:
* controlled dependency installation

13. System vision (final architecture)
End state:
Teams
* maintain full internal applications
* expose “cockpit export layer” (cards)
Cards
* atomic insight units
* reusable across pages and contexts
* consistent interface across organisation
Pages
* compositions of cards
* either curated (team-defined) or flexible (user-defined)
Cockpit
* single Dash runtime
* registry of all cards
* rendering engine + layout system
* executive-level overview system

14. Key design principles
1. Cards are the atomic UI primitive
2. Pages are compositions of cards
3. Teams own data, not cockpit
4. Cockpit owns presentation, not logic
5. Failures are isolated per card
6. System is startup-loaded, not dynamic
7. Simplicity over runtime flexibility

15. Implementation phases (recommended order)
Phase 1: Minimal cockpit
* Dash app shell
* card registry
* 1–2 example cards from one team
* basic grid rendering
* error isolation

Phase 2: Multi-team integration
* install multiple packages
* standardise get_cards()
* validate registry integrity

Phase 3: Page system
* static pages (card lists)
* navigation between pages

Phase 4: User-defined layouts
* config-driven layouts
* optional personalization layer

Phase 5: Hardening
* monitoring
* logging per card
* performance constraints
* caching if needed

Final summary
You are building:
A cards-first executive analytics cockpit where teams publish self-contained insight units, and pages are simply structured compositions of those cards, all running in a single Dash application with strict isolation and graceful failure handling.
