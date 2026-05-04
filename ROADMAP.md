# dash-cockpit — Roadmap & Architecture Outlook

This document is an honest picture of where the cockpit stands, what's still rough, and what we should build (or pin down) next. It complements `CLAUDE.md` (which is the design reference) by adding an explicit forward-looking plan.

---

## Where we are today

**Shipped:**

- **Core protocol.** `Card` (`runtime_checkable`) + `CardMeta` (TypedDict, validated at registration). `RenderContext` (TypedDict, all-optional, populated per request from Flask state — `Accept-Language` → `locale`, `X-Request-ID` → `request_id`, `flask.g.cockpit_user` → `user`).
- **Three page types.** `TeamPage` (drag-drop grid), `UserPage` (fixed Bootstrap rows, no persistence), `ConfiguratorPage` (runtime composition).
- **Multi-team registry.** `CardRegistry.load_packages([...])` with startup-time validation, failed-card error isolation via `error_boundary`, and **per-package import isolation** (pin-down #7) — one broken team package gets recorded in `registry.failures()` and `warnings.warn`'d at startup; other packages still load. `strict=True` opts back into fail-fast.
- **Drag-drop + sizing.** `dash-snap-grid` (isolated in [_packing.py](src/dash_cockpit/_packing.py) so it can be swapped). 12-column raster, square unit cells (`rowHeight = column pixel width`), localStorage persistence per browser/page. `CockpitApp(content_max_width=1600)` caps + centers content on ultra-wide displays.
- **Cockpit-owned card chrome.** `card_chrome(body, ...)` in [_chrome.py](src/dash_cockpit/_chrome.py): border, rounded corners, body container, and a floating top-right `…` menu (`dmc.ActionIcon` overlay, no header bar). Cards render *body only*; if they want a title, they draw it themselves inside the body. `CARD_META["title"]` is still consumed by the About modal and the registry — it's just not rendered by the chrome.
- **Tier 1 polish.** Edit-mode toggle (cards locked by default), per-card auto-refresh via `CARD_META["refresh_interval"]`, `dcc.Loading` spinner on every body, `CARD_NO_DRAG_CLASS`, configurable `resize_handles`.
- **Configurator (Phase 2).** `CardTemplate` + `ParameterSpec` (`select` / `multi_select` / `number` / `date` / `text`), cascading `options_fn`, deterministic `card_id_for(...)` for idempotent Add, multi-select `fanout_params`. Per-card `…` actions emit pattern-matching callback events.
- **Export pipeline.** `TabularCard` / `DocumentCard` / `ChartCard` opt-in protocols, generic `ExportBackend`. Configurator-aware (exports the live working list, not the static `card_ids`).
- **Preset library (M1).** Generic group-namespaced `Preset(name, group, entries, ...)`; `PresetStore` protocol; in-memory + filesystem implementations; three optional callable providers (visibility, writability, save target) with env-var defaults from `$COCKPIT_USER`. Seed presets are read-only and respect visibility. Layout snapshotting + delete UI deferred.
- **Slug routing + shareable URLs (M1.5).** Pages at `/<slug>`; duplicates raise at startup. `?b=<base64>` (inline ad-hoc bundle) and `?preset=<group>/<name>` (deep-link via `PresetStore`). Share button copies `?b=` clientside. URL hydration is empty-only (never tramples edits) and silent on missing/invisible presets (no leak via URL probing).
- **Card surfaces — body / settings / actions (M3).** `Card.render(context)` may return either a bare `Component` (legacy, treated as body-only) or a slot dict `{"body": ..., "settings": ..., "actions": {...}}`. The cockpit auto-injects three standard … items via `card_chrome`: **Refresh** (always — re-renders body via the M2 path), **About** (always — opens an app-level modal with title + description + team + optional `deep_link`), **Settings** (only when render returned a `settings` slot — opens a right-edge `dbc.Offcanvas` whose body is the re-rendered settings panel). Custom actions appear above standard items separated by a divider. `CARD_META["actions"]` stays valid as a static default.
- **UI library — `dash-mantine-components` (M5.5).** Cockpit shell is `dmc.AppShell` (header + navbar + main); per-card `…` menu, About modal, and Settings drawer are all dmc; `pack_row` uses `dmc.Grid`; configurator forms use `dmc.Select` / `dmc.NumberInput` / `dmc.TextInput`; the whole tree is wrapped in `dmc.MantineProvider`. `dash-bootstrap-components` removed from dependencies.
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

### M5.5 — Port from `dash-bootstrap-components` to `dash-mantine-components` — ✅ shipped

The cockpit's runtime UI is now fully on `dash-mantine-components`. `dash-bootstrap-components` is dropped from dependencies.

**Touched modules and what changed:**

- `_app.py`: hand-rolled flexbox shell → `dmc.AppShell` (header + navbar + main); export modal → `dmc.Modal` + `dmc.RadioGroup`; nav links → `dmc.NavLink` with a pattern-matching `active`-by-URL callback (replaces `dbc.NavLink(active="exact")`'s built-in behaviour); edit-mode switch → `dmc.Switch` (`checked` prop, not `value`).
- `_chrome.py`: per-card `…` menu → `dmc.Menu` + `dmc.MenuTarget` + `dmc.MenuDropdown` + `dmc.MenuItem`; About modal → `dmc.Modal`; Settings drawer → `dmc.Drawer` (right-edge); the action-shape contract (`{id: str | dict}`) is unchanged so card authors are unaffected.
- `_packing.py`: `pack_row` → `dmc.Grid` + `dmc.GridCol` (`UserPage` rows). 12-column system is identical to Bootstrap's so `col_width()` stays shape-stable.
- `_configurator.py`: parameter form widgets (`dbc.Input` / `dcc.Dropdown`) → `dmc.NumberInput` / `dmc.TextInput` / `dmc.Select` / `dmc.MultiSelect`; sidebar buttons → `dmc.Button`. `dcc.DatePickerSingle` left as-is (Dash core).
- `_presets.py`: save modal → `dmc.Modal`; preset picker → `dmc.Select` (`data` prop, not `options` — callback updated).
- `CockpitApp.theme` is now `Optional[str] = None` (was `dbc.themes.BOOTSTRAP`). Pass a Bootstrap-theme URL only if your card bodies still rely on Bootstrap utility classNames.
- The whole tree is wrapped in `dmc.MantineProvider` for Mantine's theming context.

**Comes for free with the port (deferred until requested):**

- Collapsible sidebar — one prop change on `AppShell` (`navbar={"breakpoint": "sm", "collapsed": {"mobile": True}}`).
- Mantine's polished default visuals — modal/drawer transitions, focus rings, dark-mode readiness via `MantineProvider(theme=...)`.

**Tests:** 223 → 223 still passing. The handful of tests that introspected `dbc.*` types (`dbc.DropdownMenuItem`, `dbc.Modal`, `dcc.Dropdown` for the preset picker) were updated to introspect their dmc counterparts.

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

### 2. Card identity stability — deferred

`CARD_META["id"]` is the React key, the URL fragment, and the localStorage key for layout. Renaming a card breaks every saved layout that referenced it. The proposed convention is `<team>:<card>` (e.g. `finance:revenue_trend`) plus `CARD_META["aliases"]: list[str]` for one-release backwards-compat on renames.

**Why deferred:** the demo today has ~24 cards across 3 teams; the cost of migrating now is small but the cost of *not* migrating is also small (no production users yet, no real layouts to break). Re-evaluate when:

- A second deployment exists with overlapping card-id namespace risk.
- Or a card gets renamed and we feel the pain of breaking saved layouts / shared `?b=` URLs.

When that happens, the work is: pick a convention, migrate demo IDs, add alias resolution in `CardRegistry.get` (look up by id, fall back to checking `aliases` lists), document it in the team contract.

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

### 5. Layout state versioning — deferred (versioning-by-key already in place)

Layouts saved in `localStorage` are tied to the current shape. The current convention is **schema-version-by-key**: the `persist_key` namespace gets bumped (`team:` → `team-v2:` happened when we invalidated stale card-size layouts). Old keys become unreachable, the new code only ever sees fresh data, no migration code lives in the codebase. Users lose their layouts on shape bumps — acceptable given infrequent bumps and the executive-cockpit use case (small user base, not the kind of place where layouts represent hours of curation).

**Options considered, in order of cost:**

1. **Drop persistence** — drag/resize per-session only. Rejected: forces users to re-run layouts every reload.
2. **Versioning-by-key (current).** Bump the `persist_key` prefix on shape changes; old keys are abandoned. ~0 lines.
3. **Versioning-by-JSON** — wrap saves as `{"version": 1, "layout": [...]}` plus a migration registry in `_packing.py`. Survives shape changes. ~30 lines.
4. **Server-side via `PresetStore`** — drop localStorage, persist layouts as auto-presets per user (the existing `Preset.layout` field, finally wired). Survives browsers. ~50 lines, requires a configured `PresetStore`.

Revisit (3) or (4) if user complaints about lost layouts become real, or if the cockpit ever hosts hand-curated multi-card pages. Until then, key-versioning is sufficient.

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
| **Robust to layout schema drift** | ➖ | Versioning-by-key (`persist_key` prefix bump) is in place; full migration deferred — pin-down #5 |
| **Versionable cards/templates** | ➖ | Pin-downs #2 and #3 deferred — revisit on first rename / multi-deployment |

---

## Recommended next-session focus

Pin-down status:

- **#1 (`RenderContext`)** — ✅ resolved.
- **#7 (package import isolation)** — ✅ resolved.
- **#5 (layout-state versioning)** — ➖ deferred (versioning-by-key is sufficient).
- **#2 (card-id namespacing)** — ➖ deferred (no production deployments yet; revisit on first rename or second deployment).
- **#3, #4, #6, #8** — not yet looked at; see sections above.

With the load-bearing decisions either resolved or consciously deferred, the next session can either:

- Pick up smaller carry-overs (preset delete UI, layout snapshotting in presets — both ~1 hour each).
- Tackle the still-open pin-downs (#6 failure budget — render timeouts; #8 `CockpitConfig` dataclass for kwargs consolidation).
- Or move into M4 / M5 / M6 territory once a real deployment provides concrete pressure.

Defer M4 (`dash-fn-form` swap), M5 (auth/logging/caching), M6 (MkDocs) until the cockpit is deployed in anger. Premature investment there is a recipe for rewriting good infrastructure for fictional needs.
