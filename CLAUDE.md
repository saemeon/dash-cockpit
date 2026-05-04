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

## Widget sizing

Pages are N-column widget grids with **square unit cells** (macOS-widget style):

- `TeamPage` / `ConfiguratorPage` declare `columns: int` (default `12`).
- Each `Card` may declare `size=(w, h)` in `CARD_META`. Default `(1, 1)`.
- Cards auto-place left-to-right, wrapping at `columns`. Users can drag/resize at runtime.
- A clientside callback measures each grid's column pixel width and sets `rowHeight` equal to it, so `(1, 1)` is a true square; aspect ratios stay constant across viewports. Floor at `SQUARE_CELL_FLOOR = 80px`.
- Card bodies must use `height: 100%` or flex layout — fixed pixel heights will clip.

## Implementation status

- **Phases 1–3.6 (foundations):** ✅ shipped.
  - **Phase 1 — Export wiring:** `TabularCard` / `DocumentCard` / `ChartCard` / `ExportBackend` protocols (all `runtime_checkable`, opt-in); `export_page()`; `CockpitApp(export_backends=...)` wires download button + format modal.
  - **Phase 2 — Configurator:** `CardTemplate` + `ParameterSpec` (types `select` / `multi_select` / `number` / `date` / `text`); `options_fn` cascading dropdowns; deterministic `card_id_for(template_id, params)` for idempotent Add; multi-select `fanout_params` (one card per scalar value, cartesian product); `ConfiguratorPage` dispatch in `render_page`. Per-card `⋮` actions emitted as pattern-matching callback events.
  - **Phase 3 — Drag-drop + sizing:** `dash-snap-grid` engine in [_packing.py](src/dash_cockpit/_packing.py); per-browser localStorage layout persistence; `CardMeta.size` flows into initial layout. `UserPage` stays on Bootstrap rows (its 2D `layout` is the source of truth — no drag-drop).
  - **Phase 3.5 — Tier 1 polish:** edit-mode toggle (cards locked by default; ⋮ menus hidden via CSS); per-card auto-refresh via `CARD_META["refresh_interval"]` + pattern-matching `dcc.Interval`; `dcc.Loading` spinner around every body; `CARD_NO_DRAG_CLASS` constant + auto-cancel for `input`/`button`/`select`/`textarea`/`a`; configurable `resize_handles`.
  - **Phase 3.6 — Slug routing:** each page at `/<slug>` (slug = `page.id` else slugified `name`); duplicate slugs raise `ValueError` at construction; `/` and unknown slugs resolve to the first page.
- **Phase 4 — Preset library (M1):** ✅ shipped — generic group model.
  - `Preset(name, group, entries, layout?, description, metadata)`, JSON round-trippable, `(group, name)` composite key. `PresetStore` protocol with `list_presets` / `save` / `load(group, name)` / `delete(group, name)`. Storage-agnostic — implementations enforce group access control; permission violations raise `PermissionError`.
  - **Generic group model.** No prescribed taxonomy — deployments invent their own strings (`"global"`, `"team:finance"`, `"user:alice"`, …).
  - Two implementations: `InMemoryPresetStore` (no filtering, for tests), `LocalFilePresetStore` (per-group subdirs, atomic writes, three optional callable providers `visible_groups_provider` / `writable_groups_provider` / `default_save_group_provider`, env-var defaults reading `$COCKPIT_USER`). Group sanitisation prevents path-traversal.
  - Seed presets layered in-memory on top of disk, filtered by visibility. Saving/deleting a seeded entry raises `PermissionError`.
  - `CockpitApp(preset_store=...)` adds a Load/Save section to every `ConfiguratorPage` sidebar.
  - **Deferred:** layout snapshotting (the `Preset.layout` field exists but is not populated on save); delete UI.
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
- **Phase 4.8 — `RenderContext` shape pinned (ROADMAP pin-down #1):** ✅ shipped.
  - New `RenderContext` `TypedDict` in `_card.py` with four `NotRequired` fields: `user`, `locale`, `page_filters`, `request_id`. Frozen contract — adding fields is forward-compatible, renaming or removing any breaks every team.
  - `CockpitApp._build_render_context()` assembles the dict per request from Flask state: `Accept-Language` → `locale`, `X-Request-ID` (or `flask.g.cockpit_request_id`) → `request_id`, `flask.g.cockpit_user` → `user`. Outside a request context (tests, scripts) returns `{}`.
  - Threaded through every `Card.render` call site: `_app` → `render_page` (page-load callback) and `register_configurator_callbacks` (working-list re-render callback) and `register_refresh_callbacks` (per-card interval callback).
  - Cards must read defensively (`context.get("locale", "en")`); reading `context["user"]` directly raises `KeyError` in unauthenticated deployments. Documented in README "The `context` argument".
- **Phase 5 (next, optional):** `Card.render_settings()` for runtime per-card settings (cardcanvas-style settings drawer — see RESEARCH_NOTES Tier 2.1), drag-from-palette flow, layout snapshotting in presets, preset delete UI.

## Known limitations / honest caveats

- **The configurator form is bespoke, not dash-fn-form.** Originally planned to use `dash-fn-form` (already in the workspace) for parameter rendering; v1 uses dbc/dcc directly. Revisit before scope grows.
- **Live callbacks are not unit-test covered.** Pure helpers and the rendered component tree are covered; configurator and layout-persistence callbacks need a running Dash app to exercise. A Selenium/integration smoke test is the next step.
- **No export-format validation.** A backend handed a page with no compatible cards is responsible for handling it (the demo writes a `README.txt`). A more opinionated cockpit would gray out incompatible formats in the modal.
- **No render timeout / payload size limit.** A card that runs forever or returns 10 MB of DOM has no per-card budget. Pin-down #6 covers the design.
- **Team package imports are not isolated.** `CardRegistry.load_packages([...])` imports arbitrary Python; a buggy team can crash startup. Pin-down #7 covers the fix (try/except per package + "broken team" placeholder).

---

## Original brief

The cockpit started from a one-page brief framing it as a *management abstraction layer over existing team apps*: read-oriented, signal-driven, single Dash runtime, multi-team, with strict per-card failure isolation. Teams keep their full internal apps; the cockpit only consumes a `get_cards()` export.

Every load-bearing decision from that brief is reflected in the code and the sections above:

- *Cards-first protocol with `render(context)` + `CARD_META`* — [_card.py](src/dash_cockpit/_card.py).
- *Failure isolation* — [_error.py](src/dash_cockpit/_error.py) wraps every render in `error_boundary`.
- *Pages are compositions of cards* — three concrete `Page` types in [_page.py](src/dash_cockpit/_page.py), unified dispatch in [_layout.py](src/dash_cockpit/_layout.py).
- *Team-owned data, cockpit-owned presentation* — `CardRegistry.load_packages([...])` in [_registry.py](src/dash_cockpit/_registry.py); cards fetch independently.
- *Startup-loaded, not dynamic* — packages are imported at construction; no runtime plugin discovery.

Everything else (drag-drop, configurator, presets, URL sharing, chrome, square cells, `RenderContext`) is plumbing layered on top — see "Implementation status" above.
