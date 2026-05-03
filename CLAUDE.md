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
- **Cards are independent of each other.** No cross-card state, no callbacks reaching across. (Like widgets.) But *within* a card, anything Dash supports is fine: a card may bundle a date picker with two charts, run its own callbacks, hold internal `dcc.Store`s, fetch from any backend. The boundary is between cards, not inside one. Need a "group of related views"? Ship them as one larger card (`size=(2, 2)`) — that's the composite pattern.
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

**Decision: adopted `dash-snap-grid` (the engine CardCanvas uses internally) as the layout layer.**

Single isolated module owns it: `_packing.py` is the only place that knows about Bootstrap row/col or `dash-snap-grid`'s `Grid`. Swapping engines later means rewriting one file.

- `pack_grid()` returns `Div([Store, Grid])` with pattern-matching dict ids.
- `register_layout_callbacks(app)` registers two clientside callbacks (`MATCH` on the grid id) that save to `dcc.Store(storage_type="local")` and restore from it on hydrate.
- A JSON equality guard in restore breaks the save→restore→save loop.
- Card's `size` (widget grid units) flows from `CARD_META["size"]` through to the grid's initial layout.

---

## Widget sizing — shipped

Pages are N-column widget grids:

- Each `TeamPage` and `ConfiguratorPage` declares `columns: int` (default 2).
- Each `Card` may declare `size=(width_units, height_units)` in `CARD_META`. Default `(1, 1)`.
- Cards auto-place left-to-right, wrapping at `columns`.
- Cells fill exactly `row_height × h` pixels (default `row_height=280`). Cards must use `height: 100%` or flex layout — fixed pixel heights will clip or leave whitespace.

## Implementation status

- **Phase 1 — Export wiring:** ✅ shipped.
  - Protocols: `TabularCard`, `DocumentCard`, `ChartCard`, `ExportBackend`. All `runtime_checkable`, all opt-in.
  - `export_page(page, registry, backend) -> bytes`; backends consume `PageExportData` (frozen dataclass).
  - `CockpitApp(export_backends={"label": backend})` adds a download button + format-radio modal.
  - Demo: `revenue_trend` is a `TabularCard`; `examples/demo_cockpit/csv_zip_backend.py` exports any `TabularCard` page as a zip of CSVs.
- **Phase 2 — Configurator:** ✅ shipped.
  - `CardTemplate` protocol with `TemplateMeta` and `ParameterSpec` (types: `select`, `multi_select`, `number`, `date`, `text`).
  - `ParameterSpec.options_fn` is wired — cascading dropdowns rerender the form on parameter change while preserving entered values.
  - `card_id_for(template_id, params)` — deterministic, order-insensitive id; idempotent Add.
  - `fanout_params` — multi-select expands cartesian-product into one card per scalar value (kennzahlen pattern).
  - `ConfiguratorPage` is in the `Page` union; `_layout.render_page` dispatches to it.
  - `_configurator.py` provides server-side rendering + Dash callbacks (template picker → form swap → store mutation → cards-pane re-render). Working-list state lives in a session `dcc.Store`.
  - Per-card actions: cards declare `actions: [{"id": ..., "label": ...}]` in `CARD_META` and the cockpit renders them as `⋮` menu items, emitting pattern-matching callback events.
  - Export modal is configurator-aware: when on a `ConfiguratorPage`, it exports the live working list, not the page's static `card_ids`.
- **Phase 3 — Drag-drop layout + widget sizing:** ✅ shipped.
  - `dash-snap-grid` is the layout engine for `TeamPage` and `ConfiguratorPage` working lists.
  - Drag/resize at runtime; layout persists per-browser via `dcc.Store(storage_type="local")`.
  - `CardMeta.size` initial hints flow through `pack_grid(sizes=...)`.
  - `UserPage` deliberately remains on Bootstrap rows (no drag-drop) — its 2D `layout` is the source of truth.
- **Phase 3.5 — Polish (Tier 1 from RESEARCH_NOTES):** ✅ shipped.
  - **Edit mode toggle**: sidebar switch flips draggable/resizable across all grids; ⋮ menus hidden via CSS unless edit mode is on. State persisted in localStorage. Cards locked by default — protects against accidental reshuffle.
  - **Per-card refresh**: cards declare `refresh_interval` seconds; one pattern-matching server callback re-renders each card on its own `dcc.Interval` tick. `0` disables (default).
  - **Loading spinner**: every card body wraps in `dcc.Loading` so slow re-renders show a spinner instead of looking frozen.
  - **`card-no-drag` class**: exposed as `CARD_NO_DRAG_CLASS` constant for card authors to opt interactive children out of drag-start. Standard HTML interactives (input/button/select/textarea/a) are excluded automatically.
  - **Configurable resize handles**: `pack_grid(resize_handles=[...])` lets users resize from any edge. Defaults to dash-snap-grid's `["se"]`.
- **Phase 3.6 — Slug-based page routing:** ✅ shipped (M1.5 sub-task A).
  - Each page is addressable at `/<slug>`. Slug = `page.id` if set, else `slugify(page.name)` (lowercased, non-alnum → `-`).
  - All three page dataclasses (`TeamPage`, `UserPage`, `ConfiguratorPage`) gained an optional `id: str = ""` field.
  - `CockpitApp.__init__` builds `_pages_by_slug`; **duplicate slugs raise `ValueError`** at construction (governance over silent overwrite, matches the registry's startup-time validation pattern).
  - Empty slugs (e.g. page name was all punctuation) raise `ValueError` — the author must set `page.id` explicitly.
  - Replaces the previous int-index routing (`/0`, `/1`). `/` and unknown slugs both resolve to the first page (preserves the previous default behaviour for the root path).
- **Phase 4 — Preset library (Bibliothek):** ✅ shipped (v2 — generic group model).
  - `Preset` dataclass: `name`, `group: str` (opaque namespace), `entries`, optional `layout`, `description`, `metadata`. JSON-round-trippable. `(group, name)` is the composite key.
  - `PresetStore` protocol with `list_presets` / `save(preset)` / `load(group, name)` / `delete(group, name)`. Storage-agnostic — the cockpit never touches storage directly. Implementations are responsible for group-based access control (visibility, write permission); calls that violate permission raise `PermissionError`.
  - **Generic group model.** The framework prescribes no taxonomy. Deployments invent their own group strings (`"global"`, `"team:finance"`, `"user:alice"`, `"region:apac"`, …). Per-user scoping is just one convention.
  - Two implementations: `InMemoryPresetStore` (no group filtering, for tests/demos), `LocalFilePresetStore` (one JSON file per preset under `<dir>/<sanitised-group>/<sanitised-name>.json`, atomic writes).
  - **Three optional providers on `LocalFilePresetStore`:** `visible_groups_provider`, `writable_groups_provider`, `default_save_group_provider`. All callables, invoked per-op so they can read request-scoped state.
  - **Env-var defaults.** When providers are omitted, the store reads `$COCKPIT_USER` (configurable via `user_env_var`) and assembles sensible defaults: visible = `["global", f"user:{u}"]`, writable = `[f"user:{u}"]`, save target = `f"user:{u}"`. With no env user: visible = `["global"]`, writable = `[]` (no saves possible).
  - **Seed presets** (in-memory, layered on top of disk) replace the old `curated=` arg. Filtered by visibility same as disk presets. Saving/deleting a seeded `(group, name)` raises `PermissionError`.
  - Group sanitisation prevents path-traversal (`"../../../etc"` becomes `"_______etc"`).
  - `CockpitApp(preset_store=...)` enables a preset section in every `ConfiguratorPage` sidebar (picker labels = `"group / name"`, Load button, Save modal showing the destination group).
  - Save callback writes to `default_save_group_provider()`; overwrites by `(group, name)`.
  - Layout snapshotting in presets is **not yet wired** (the `layout` field exists on `Preset` but the save callback only stores `entries`). Follow-up.
  - Delete UI is **not yet wired** (only the storage protocol supports it). Follow-up.
- **Phase 4.5 — URL routing & shareable views (M1.5):** ✅ shipped.
  - New module `_share.py` defines the bundle wire format: `list[{"template_id": str, "params": dict}]` — same shape as `WORKING_LIST_STORE_ID.data` and `Preset.entries`. No new dataclass.
  - `encode_bundle` / `decode_bundle` round-trip a working list through urlsafe-base64-no-padding JSON. `sort_keys=True` for deterministic tokens.
  - `resolve_from_search(search, preset_loader)` dispatches `?b=<base64>` (inline ad-hoc) and `?preset=<group>/<name>` (deep-link via the existing `PresetStore`). Bare `?preset=<name>` is shorthand for `group=""`. `?b` wins when both present; malformed `?b` falls through to `?preset` for graceful degradation.
  - URL hydration callback in `_configurator.py` seeds `WORKING_LIST_STORE_ID` from the URL on first render only — once the user has cards, the URL is ignored. `KeyError` and `PermissionError` from the preset loader are both swallowed silently to avoid leaking presence-vs-permission via URL probing.
  - Share button (configurator sidebar) builds a `?b=...` URL clientside (canonical-key JSON, urlsafe base64, no padding) and copies it to clipboard. Long-URL warning above ~2000 chars suggests a preset instead.
  - Status messages target `STATUS_ID` (always present) rather than `PRESET_STATUS_ID`, so URL hydration and Share work in deployments without a configured preset store.
- **Phase 4.6 — Cockpit-owned card chrome:** ✅ shipped.
  - New module `_chrome.py` defines `card_chrome(body, *, card_id, title, actions, extra_menu_items)` — the standard frame around every card body: border, rounded corners, header with title and ⋮ menu, body container with `flex: 1` + `overflow: auto`.
  - `_layout.py._resolve_card` and `_configurator.py._render_card_tile` both wrap card bodies in `card_chrome` instead of returning bare bodies. The configurator passes a "Remove" item via `extra_menu_items`.
  - Card protocol narrowed: `render(context)` returns the *body only*. Teams must not produce their own border, title, or outer padding — that's the cockpit's job. Existing demo cards updated (H6 titles + outer Divs removed).
  - Per-card menus now live in the chrome header (not absolute-positioned overlays). Edit-mode visibility CSS (`CARD_MENU_CLASS`) still applies.
- **Phase 4.7 — Density tuning + square unit cells:** ✅ shipped.
  - Default `columns` raised from `2` to `6` (`TeamPage`, `ConfiguratorPage`) — denser raster, closer to macOS-widget feel.
  - **Square unit cells.** `register_square_cell_callbacks` (clientside) measures each grid's column pixel width and writes it back as `rowHeight`. A `(1, 1)` card is therefore a true square; `(2, 1)` is 2:1 wide; `(1, 2)` is 1:2 tall; `(2, 2)` is a 2× square. Aspect ratios stay constant across viewport sizes — only the absolute pixel size of the unit cell changes. Floor at `SQUARE_CELL_FLOOR = 80px` so very narrow viewports don't produce sub-readable cells. Window resize triggers re-measure via `GRID_RESIZE_TICK_ID` store + a one-time `window.addEventListener('resize', ...)` using `dash_clientside.set_props`.
  - **No viewport-fill.** We tried stretching `rowHeight` to make total grid height fill the viewport, and reverted — stretched cards felt wrong (a `(2, 2)` card on a 2-row page took the entire screen). iOS/Bloomberg both use fixed pixel sizes; empty space below sparse pages is honest. See `RESEARCH_NOTES.md` "Card sizing".
  - **`CockpitApp(content_max_width=1600)`.** Page-content area is capped (default 1600px) and centered, preventing card spread on ultra-wide monitors. `content_max_width=None` opts out (legacy `flex: 1` behaviour).
  - Grid margins tightened from `[10, 10]` to `[6, 6]` for a denser look.
  - Named-size vocabulary (`"small" / "wide" / "tall" / "medium" / ...`) is **not** shipped yet; deferred pending real usage signals (see `RESEARCH_NOTES.md` "Card sizing — options for later evaluation").
- **Phase 5 (next, optional):** `Card.render_settings()` for runtime per-card settings (cardcanvas-style settings drawer — see RESEARCH_NOTES Tier 2.1), drag-from-palette flow, layout snapshotting in presets, preset delete UI.

## Known limitations / honest caveats

- **The configurator form is bespoke, not dash-fn-form.** Originally planned to use `dash-fn-form` (already in the workspace) for parameter rendering; v1 uses dbc/dcc directly. Revisit before scope grows.
- **Live callbacks are not unit-test covered.** Pure helpers and the rendered component tree are covered; configurator and layout-persistence callbacks need a running Dash app to exercise. A Selenium/integration smoke test is the next step.
- **No export-format validation.** A backend handed a page with no compatible cards is responsible for handling it (the demo writes a `README.txt`). A more opinionated cockpit would gray out incompatible formats in the modal.
- **`refresh_interval` is documented but not yet wired.** Cards declare it in `CARD_META` but the cockpit does not auto-refresh.

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

The boundary is between cards, not inside them. Within a single card, do anything Dash supports — internal state, callbacks, sub-components, even a small form-and-chart pair. Cards may take more grid space (`CARD_META["size"] = (2, 1)` or larger) to host richer compositions; the "one card per insight" rule is about cohesion, not literal size.

What is *not* supported: cross-card interactions, callbacks that reach across cards, or global state shared between cards. Three views that must share state ship as one larger composite card, not three coupled cards. This is what makes per-card error isolation, deterministic `card_id_for(...)`, and the iOS-widget mental model all work.

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
