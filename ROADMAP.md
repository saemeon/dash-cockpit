# dash-cockpit — Roadmap & Architecture Outlook

This document is an honest picture of where the cockpit stands, what's still rough, and what we should build (or pin down) next. It complements `CLAUDE.md` (which is the design reference) by adding an explicit forward-looking plan.

---

## Where we are today

**Shipped:**

- **Core protocol.** `Card` (`runtime_checkable`) + `CardMeta` (TypedDict, validated at registration). `RenderContext` (TypedDict, all-optional, populated per request from Flask state — `Accept-Language` → `locale`, `X-Request-ID` → `request_id`, `flask.g.cockpit_user` → `user`).
- **Three page types.** `TeamPage` (drag-drop grid), `UserPage` (fixed Bootstrap rows, no persistence), `ConfiguratorPage` (runtime composition).
- **Multi-team registry.** `CardRegistry.load_packages([...])` with startup-time validation, failed-card error isolation via `error_boundary`, and **per-package import isolation** (pin-down #7) — one broken team package gets recorded in `registry.failures()` and `warnings.warn`'d at startup; other packages still load. `strict=True` opts back into fail-fast.
- **Drag-drop + sizing.** `dash-snap-grid` (isolated in [_packing.py](src/dash_cockpit/_packing.py) so it can be swapped). 12-column raster, square unit cells (`rowHeight = column pixel width`), localStorage persistence per browser/page. `CockpitApp(content_max_width=1600)` caps + centers content on ultra-wide displays.
- **Cockpit-owned card chrome.** `card_chrome(body, ...)` in [_chrome.py](src/dash_cockpit/_chrome.py): border, header with title + … menu, body container. Cards return *body only*.
- **Tier 1 polish.** Edit-mode toggle (cards locked by default), per-card auto-refresh via `CARD_META["refresh_interval"]`, `dcc.Loading` spinner on every body, `CARD_NO_DRAG_CLASS`, configurable `resize_handles`.
- **Configurator (Phase 2).** `CardTemplate` + `ParameterSpec` (`select` / `multi_select` / `number` / `date` / `text`), cascading `options_fn`, deterministic `card_id_for(...)` for idempotent Add, multi-select `fanout_params`. Per-card `…` actions emit pattern-matching callback events.
- **Export pipeline.** `TabularCard` / `DocumentCard` / `ChartCard` opt-in protocols, generic `ExportBackend`. Configurator-aware (exports the live working list, not the static `card_ids`).
- **Preset library (M1).** Generic group-namespaced `Preset(name, group, entries, ...)`; `PresetStore` protocol; in-memory + filesystem implementations; three optional callable providers (visibility, writability, save target) with env-var defaults from `$COCKPIT_USER`. Seed presets are read-only and respect visibility. Layout snapshotting + delete UI deferred.
- **Slug routing + shareable URLs (M1.5).** Pages at `/<slug>`; duplicates raise at startup. `?b=<base64>` (inline ad-hoc bundle) and `?preset=<group>/<name>` (deep-link via `PresetStore`). Share button copies `?b=` clientside. URL hydration is empty-only (never tramples edits) and silent on missing/invisible presets (no leak via URL probing).
- **Card surfaces — body / settings / actions (M3).** `Card.render(context)` may return either a bare `Component` (legacy, treated as body-only) or a slot dict `{"body": ..., "settings": ..., "actions": {...}}`. The cockpit auto-injects three standard … items via `card_chrome`: **Refresh** (always — re-renders body via the M2 path), **About** (always — opens an app-level modal with title + description + team + optional `deep_link`), **Settings** (only when render returned a `settings` slot — opens a right-edge `dbc.Offcanvas` whose body is the re-rendered settings panel). Custom actions appear above standard items separated by a divider. `CARD_META["actions"]` stays valid as a static default.
- **Demo app.** `examples/demo_cockpit/` with three teams (`team_finance`, `team_ops`, `team_sizes`); the **Size Sampler page** renders one tile per `(w, h)` from `1×1` up to `12×4` for visual size reference.

**Tested:** 223 tests, ~77% coverage. Pure helpers, store CRUD with group filtering, env-var defaults, rendered component trees, callback registration, share codec, slug routing, and `RenderContext` assembly are covered. Live Dash callback bodies (configurator mutations, layout persistence, edit-mode apply, refresh re-render, preset load/save, URL hydration) are smoke-tested only — Selenium/integration coverage is the next gap.

---

## Future direction — milestones in priority order

> M1, M1.5, M2, M3 — shipped. See "Where we are today" above and `CLAUDE.md` "Implementation status" for the per-phase detail.

### M4 — `dash-fn-form` for parameter rendering

The configurator currently builds its own form with `dbc.Input` / `dcc.Dropdown`. The workspace already has `dash-fn-form` which does this from type hints. Switching saves code and gives consistent polish (validation, error display, conditional fields).

**Why later:** the bespoke form works; this is investment in maintainability, not features.

**Risk:** `dash-fn-form` may not handle all our `ParameterType` values (especially `multi_select` fan-out semantics). Validate with a spike before committing.

### M5 — Deployment & operational story

Today the cockpit is an in-process Dash app. For real corporate deployment we need:

- **Auth integration**: SAML/OIDC at the Flask level. Per-page or per-card visibility based on user attributes (`team`, `role`).
- **Logging**: structured per-card logs with team tag for routing. A failed `revenue_card` should page the finance on-call, not platform.
- **Caching**: a per-card response cache (key: `(card_id, context)`, TTL: `refresh_interval`). Without this, every navigation re-fetches.
- **Health endpoint**: `/healthz` that exercises the registry but not card data fetches.

These are not deep design issues — they're "set up the boring infrastructure" tasks. Bundle into one phase when the cockpit is deployed in anger.

### M5.5 — Port from `dash-bootstrap-components` to `dash-mantine-components`

The cockpit shell is hand-rolled flexbox in [_app.py](src/dash_cockpit/_app.py) and hand-rolled CSS in [_chrome.py](src/dash_cockpit/_chrome.py); collapsible sidebar, settings drawer, and notifications are all DIY. `dmc.AppShell` ships a real layout primitive (collapsible navbar + header + main + footer), `dmc.Card` / `dmc.Menu` replace the chrome CSS, `dmc.Modal` replaces `dbc.Modal`, and Mantine's defaults are visually nicer than Bootstrap's.

**Scope:** wholesale, not piecemeal. Mixing `dbc.Button` next to `dmc.Button` looks off and produces theme drift. Touched modules: `_app.py` (shell + sidebar + export modal), `_chrome.py` (card frame + … menu), `_configurator.py` (form inputs, save modal, status pills), `_packing.py` (only the wrapper Divs — `dash-snap-grid` is library-agnostic).

**Why later:** the cockpit isn't customer-facing yet, the API is still moving (M5 will touch the shell for auth/branding), and a wholesale rewrite under a moving API doubles the work. Do it once, all at once, after the API has stabilised and before opening up to teams.

**Defers:** sidebar collapse, notification toasts, polished modal/drawer animations. All come for free with `AppShell` + `dmc.Notifications` + `dmc.Modal` + `dmc.Drawer`.

### M6 — Documentation & gallery

The styleguide expects:

- `docs/` MkDocs site with API reference (`mkdocstrings`) and user guide.
- `examples/` directory with `mkdocs-gallery` scripts.

We have a working demo (`examples/demo_cockpit/`) but no MkDocs setup. Add when the API stabilises so we don't rewrite docs every week.

---

## Re-evaluating CardCanvas

We decided **not** to adopt CardCanvas as our foundation. Now that the cockpit is mostly shipped, almost everything CardCanvas offers we have — usually with better separation of concerns.

| CardCanvas | Our equivalent | Verdict |
|---|---|---|
| `Card` ABC with `render()` + `render_settings()` | `Card` Protocol with `render()` returning slot dict `{body, settings, actions}` (M3) | One mental model — the same dict shape covers static, settings-bearing, and dynamic-action cards. |
| Drag-drop grid (`dash-snap-grid`) | Same engine, isolated in [_packing.py](dash-cockpit/src/dash_cockpit/_packing.py) | Identical capability, less coupling. |
| Per-card menus | `CARD_META["actions"]` (static) or render-time `actions` slot (dynamic); plus auto-injected Refresh/About/Settings (M3) | Static + dynamic + cockpit-supplied standards in one menu. |
| Settings drawer | App-level `dbc.Offcanvas`, auto-opened by Settings … when card returned a `settings` slot (M3) | Shipped. |
| Share-by-URL | `?b=` and `?preset=` (M1.5) | Different shape: bundles of cards, not single cards. |
| Auto-refresh `interval` | `CARD_META["refresh_interval"]` (M2) + manual Refresh … (M3) | Shipped. |
| Card gallery / picker | `ConfiguratorPage` | Different model — we pick from templates, not card classes. |

---

## What to pin down — prerequisites for "simple, pluggable, robust"

These aren't features so much as load-bearing decisions that affect everything downstream. Resolving them now prevents painful rewrites later.

### 1. The render context dict — ✅ resolved (Phase 4.8)

`RenderContext` is a `TypedDict` in [src/dash_cockpit/_card.py](src/dash_cockpit/_card.py) with four `NotRequired` fields: `user`, `locale`, `page_filters`, `request_id`. `CockpitApp._build_render_context()` populates them per request from Flask state (`Accept-Language` header, `X-Request-ID` header, `flask.g.cockpit_user`). Cards must read defensively — `context.get("locale", "en")`, never `context["locale"]`. Documented in the README "The `context` argument" section.

`page_filters` is reserved (no filter bar yet); `user` requires auth middleware to set `flask.g.cockpit_user` (Phase M5). Adding new fields is forward-compatible; renaming or removing a field breaks every team.

### 2. Card identity stability

`CARD_META["id"]` is the React key, the URL fragment, and the localStorage key for layout. Renaming a card breaks every saved layout that referenced it.

**Pin down:**

- A naming convention: `<team>:<card>` (e.g. `finance:revenue_trend`). Prevents collisions, makes provenance obvious in logs.
- A migration path: when a team renames, ship a temporary alias in `CARD_META["aliases"]: list[str]` so old layouts keep working for one release.

### 3. Versioning of cards and templates

A team ships v1 of `revenue_card`. Six months later, the data shape changes. v2 is incompatible.

**Pin down:**

- Cards stay at one ID — the team is responsible for backwards-compatible data.
- For incompatible changes, ship as a new ID (`revenue_trend_v2`) and let the page author migrate explicitly.
- This is a discipline not a framework feature; document it loudly in the team contract.

### 4. The team contract — what counts as "publishing a card"

Today a team package needs `get_cards()` (and optionally `get_card_templates()`). That's enough but vague.

**Pin down:** a published `cockpit_team_contract.md` with:

- The exact return type of `get_cards()`.
- What can change without a major version bump (data shape inside cards) vs. what counts as breaking (id, action ids, parameter shapes).
- Test scaffolding teams should run before shipping (e.g. `cockpit-cli validate <package>`).

### 5. Layout state versioning

Layouts saved in `localStorage` are tied to the current data shape. If we rename the shape (e.g. from `{i, x, y, w, h}` to something else), users see broken layouts.

**Pin down:**

- A schema version key in the stored data: `{"version": 1, "layout": [...]}`.
- A migration function in `_packing.py` that the restore callback runs.

### 6. Failure budget

Today: a card that raises gets a red error tile. That's the right default. But:

- What about a card that runs forever? No timeout today. A 30-second slow card freezes the page render.
- What about a card that returns an enormous component (10MB DataTable)? No payload limit.

**Pin down:**

- A render timeout per card (default 5 s). Configurable in `CardMeta`.
- A dev-mode component-size warning in the browser console.
- A circuit breaker: if a card has failed 3 times in 5 minutes, stop rendering it for 1 minute. Surfaces in monitoring before users notice.

### 7. Plugin discovery and trust — ✅ resolved (Phase 4.10)

`CardRegistry.load_packages([...])` now isolates per-package failures: a buggy team's `ImportError` / `RegistryError` / `get_cards()` crash is caught, recorded in `_failures`, surfaced via `warnings.warn` at startup and `registry.failures()` programmatically. Other packages continue loading. Cards from a failed package are absent from the registry, so any page referencing them falls through to the existing "Unknown card" warning tile — same one-level-up of the per-card error-boundary pattern. `strict=True` opts back into fail-fast for tests / CI.

Subprocess-per-team isolation remains deferred — premature given typical deployments.

### 8. Configuration surface

`CockpitApp.__init__` already takes `registry`, `pages`, `title`, `theme`, `export_backends`. The next things teams will ask for:

- Custom CSS (today: pass via `theme`, but only Bootstrap themes work).
- Logo / branding in the sidebar.
- Custom 404 / error page.
- Auth config.

**Pin down:** a single `CockpitConfig` dataclass replacing the kwargs. Easier to extend without breaking existing code:

```python
@dataclass
class CockpitConfig:
    title: str = "Cockpit"
    theme: str = dbc.themes.BOOTSTRAP
    custom_css: list[str] = field(default_factory=list)
    logo_url: str | None = None
    auth: AuthConfig | None = None
    # ...future fields here
```

`CockpitApp(registry, pages, config=CockpitConfig(...))`. Keep the current kwargs as a shim for one release.

---

## "Simple, pluggable, robust" — checklist

| Property | Status | What's left |
|---|---|---|
| **Simple to write a card** | ✅ | One dict + one function. Already minimal. |
| **Simple to wire a page** | ✅ | One `TeamPage(name, card_ids)`. |
| **Pluggable layout engine** | ✅ | Swap one module (`_packing.py`). |
| **Pluggable export** | ✅ | Implement `ExportBackend.export`. |
| **Pluggable storage (presets)** | ✅ | M1 (`PresetStore` + 2 implementations) |
| **Pluggable auth** | ⏳ | M5 (`flask.g.cockpit_user` already plumbed into `RenderContext`) |
| **Shareable URLs (deep links)** | ✅ | M1.5 (`?b=`, `?preset=<group>/<name>`, slug routing) |
| **`RenderContext` shape locked** | ✅ | Pin-down #1 (`user`, `locale`, `page_filters`, `request_id`) |
| **Robust to bad cards** | ✅ | Error boundary, isolation by design. |
| **Robust to slow cards** | ❌ | Render timeout — pin down #6 |
| **Robust to bad team packages** | ✅ | Pin-down #7 (per-package try/except in `load_packages`, failures via `registry.failures()`) |
| **Robust to layout schema drift** | ⏳ | Version + migration — pin down #5 |
| **Versionable cards/templates** | ⏳ | Convention + alias mechanism — pin down #2, #3 |

---

## Recommended next-session focus

Pin-downs #1 and #7 are resolved. The remaining "free now, expensive later" decisions:

1. **Pin-down #2 — card-id namespacing.** Agree on `<team>:<card>` IDs (e.g. `finance:revenue_trend`) + `CARD_META["aliases"]: list[str]` for renames *before* any card ID gets baked into a saved layout. Includes migrating the demo IDs and adding alias resolution in `CardRegistry`. ~1 hour.
2. **Pin-down #5 — layout-state versioning.** Stamp `{"version": 1, "layout": [...]}` into `localStorage` and add a migration hook in `_packing.py` restore. Cheap to add now, brittle to retrofit once user layouts exist in the wild.

Defer M4 (`dash-fn-form` swap), M5 (auth/logging/caching), M5.5 (Mantine port), M6 (MkDocs) until the cockpit is deployed in anger. Premature investment there is a recipe for rewriting good infrastructure for fictional needs — and M5.5 in particular wants the API to stop moving first.
