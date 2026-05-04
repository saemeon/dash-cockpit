# dash-cockpit — Roadmap & Architecture Outlook

This document is an honest picture of where the cockpit stands, what's still rough, and what we should build (or pin down) next. It complements `CLAUDE.md` (which is the design reference) by adding an explicit forward-looking plan.

---

## Where we are today

**Shipped:**

- **Core protocol.** `Card` (`runtime_checkable`) + `CardMeta` (TypedDict, validated at registration). `RenderContext` (TypedDict, all-optional, populated per request from Flask state — `Accept-Language` → `locale`, `X-Request-ID` → `request_id`, `flask.g.cockpit_user` → `user`).
- **Three page types.** `TeamPage` (drag-drop grid), `UserPage` (fixed Bootstrap rows, no persistence), `ConfiguratorPage` (runtime composition).
- **Multi-team registry.** `CardRegistry.load_packages([...])` with startup-time validation; failed-card error isolation via `error_boundary`.
- **Drag-drop + sizing.** `dash-snap-grid` (isolated in [_packing.py](src/dash_cockpit/_packing.py) so it can be swapped). 12-column raster, square unit cells (`rowHeight = column pixel width`), localStorage persistence per browser/page. `CockpitApp(content_max_width=1600)` caps + centers content on ultra-wide displays.
- **Cockpit-owned card chrome.** `card_chrome(body, ...)` in [_chrome.py](src/dash_cockpit/_chrome.py): border, header with title + ⋮ menu, body container. Cards return *body only*.
- **Tier 1 polish.** Edit-mode toggle (cards locked by default), per-card auto-refresh via `CARD_META["refresh_interval"]`, `dcc.Loading` spinner on every body, `CARD_NO_DRAG_CLASS`, configurable `resize_handles`.
- **Configurator (Phase 2).** `CardTemplate` + `ParameterSpec` (`select` / `multi_select` / `number` / `date` / `text`), cascading `options_fn`, deterministic `card_id_for(...)` for idempotent Add, multi-select `fanout_params`. Per-card `⋮` actions emit pattern-matching callback events.
- **Export pipeline.** `TabularCard` / `DocumentCard` / `ChartCard` opt-in protocols, generic `ExportBackend`. Configurator-aware (exports the live working list, not the static `card_ids`).
- **Preset library (M1).** Generic group-namespaced `Preset(name, group, entries, ...)`; `PresetStore` protocol; in-memory + filesystem implementations; three optional callable providers (visibility, writability, save target) with env-var defaults from `$COCKPIT_USER`. Seed presets are read-only and respect visibility. Layout snapshotting + delete UI deferred.
- **Slug routing + shareable URLs (M1.5).** Pages at `/<slug>`; duplicates raise at startup. `?b=<base64>` (inline ad-hoc bundle) and `?preset=<group>/<name>` (deep-link via `PresetStore`). Share button copies `?b=` clientside. URL hydration is empty-only (never tramples edits) and silent on missing/invisible presets (no leak via URL probing).
- **Demo app.** `examples/demo_cockpit/` with three teams (`team_finance`, `team_ops`, `team_sizes`); the **Size Sampler page** renders one tile per `(w, h)` from `1×1` up to `12×4` for visual size reference.

**Tested:** 202 tests, 80% coverage. Pure helpers, store CRUD with group filtering, env-var defaults, rendered component trees, callback registration, share codec, slug routing, and `RenderContext` assembly are covered. Live Dash callback bodies (configurator mutations, layout persistence, edit-mode apply, refresh re-render, preset load/save, URL hydration) are smoke-tested only — Selenium/integration coverage is the next gap.

---

## Future direction — milestones in priority order

### M1 — Saved presets ("Bibliothek") — ✅ shipped

Storage-agnostic `PresetStore` with `(group, name)` keying; in-memory and filesystem implementations. Group is an opaque namespace — deployment defines the taxonomy (`global`, `team:*`, `user:*`, …). Sidebar Load/Save UI on every `ConfiguratorPage`. See [_presets.py](dash-cockpit/src/dash_cockpit/_presets.py).

**Design intent:** the cockpit owns no persistence policy. Visibility, writability, and the default save target are deployment concerns, injected as callables. The protocol stays user-agnostic; only implementations know about users.

**Deferred:** layout snapshotting (the `Preset.layout` field exists but isn't populated on save); delete UI.

### M1.5 — URL routing & shareable views — ✅ shipped

Slug-based page routing (`/<page-slug>`) replaces int-index. Configurator working lists are shareable via two URL params, both `ConfiguratorPage`-only:

```
/<page-slug>?b=<base64-json>              # inline ad-hoc working list
/<page-slug>?preset=<group>/<name>        # deep-link via PresetStore
/<page-slug>?preset=<name>                # shorthand for group=""
```

See [_share.py](dash-cockpit/src/dash_cockpit/_share.py) for the codec, [_configurator.py](dash-cockpit/src/dash_cockpit/_configurator.py) for the URL hydration callback and Share button.

**Design intent:**

- **URL = initial state, not live binding.** Hydrates only an empty working list; user edits are never trampled by URL revisits. Share is an explicit button, not implicit on every change.
- **Bundles and presets share one wire shape** (`list[{template_id, params}]`) and one consumer (the working-list store). The URL hydrator is shape-only — it doesn't know whether a bundle came from base64 or a preset name.
- **Named bundles *are* presets.** No parallel storage abstraction; `?preset=` is just a URL surface on `PresetStore`.
- **Silent on missing/invisible presets** — `KeyError` and `PermissionError` from the loader collapse to "no bundle". Never leak presence-vs-permission via URL probing.

### M2 — Per-card refresh — ✅ shipped

Cards declaring `CARD_META["refresh_interval"]` (seconds) are wrapped in their own `dcc.Interval`; one pattern-matching server callback re-renders each card on its own tick. `0` (default) disables. See [_refresh.py](dash-cockpit/src/dash_cockpit/_refresh.py).

### M3 — Card actions plumbing

Cards declare actions in `CARD_META["actions"]`; clicks fire pattern-matching events. **But:** the cockpit doesn't currently wire any handlers — teams have to register their own callbacks against the pattern-matching id. That's fine but needs documentation and a default for the common cases.

**What to pin down:**

- A standard "Refresh" action that triggers a render-cycle for that card (related to M2).
- A standard "Open in team app" action that navigates to a deep link the card declares in `CARD_META["deep_link"]`.
- An "About" action that opens a modal with `CARD_META["description"]` + team contact info.

**Scope:** small. Each is a few callback lines.

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

**Scope:** wholesale, not piecemeal. Mixing `dbc.Button` next to `dmc.Button` looks off and produces theme drift. Touched modules: `_app.py` (shell + sidebar + export modal), `_chrome.py` (card frame + ⋮ menu), `_configurator.py` (form inputs, save modal, status pills), `_packing.py` (only the wrapper Divs — `dash-snap-grid` is library-agnostic).

**Why later:** the cockpit isn't customer-facing yet, the API is still moving (M3, M5 will both touch the shell), and a wholesale rewrite under a moving API doubles the work. Do it once, all at once, after the API has stabilised and before opening up to teams.

**Defers:** sidebar collapse, settings drawer for `Card.render_settings()` (M3), notification toasts. All come for free with `AppShell` + `dmc.Notifications`.

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
| `Card` ABC with `render()` + `render_settings()` | `Card` Protocol with `render()`; settings via `CardMeta.actions` + team callbacks | More flexible primitive — settings UI isn't coupled to the card class. |
| Drag-drop grid (`dash-snap-grid`) | Same engine, isolated in [_packing.py](dash-cockpit/src/dash_cockpit/_packing.py) | Identical capability, less coupling. |
| Per-card menus | `CardMeta.actions` | Ours is opt-in and pattern-matching-friendly. |
| Settings drawer | None yet — addable as a card action that opens a modal | Open gap; small fix. |
| Share-by-URL | `?b=` and `?preset=` (M1.5) | Different shape: bundles of cards, not single cards. |
| Auto-refresh `interval` | `CardMeta.refresh_interval` (M2) | Shipped. |
| Card gallery / picker | `ConfiguratorPage` | Different model — we pick from templates, not card classes. |

**The one CardCanvas pattern worth learning from:** `render_settings()`. Cards that need user-configurable runtime state (color, threshold, time window) deserve a first-class settings UI rather than "drop your own form into the card body" or "use a configurator template". An optional `Card.render_settings()` opened by a built-in `⋮` "Settings" action would close the gap in ~30 lines.

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

### 7. Plugin discovery and trust

`CardRegistry.load_packages([...])` imports arbitrary Python — there's no isolation. A buggy team package can crash the cockpit at startup.

**Pin down:**

- Each package should load in a try/except at startup, with a "broken team" placeholder rendered for affected pages (matches the per-card failure pattern, one level up).
- Long term: consider a subprocess-per-team architecture for hard isolation. Probably overkill for now.

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
| **Robust to bad team packages** | ⏳ | Startup try/except — pin down #7 |
| **Robust to layout schema drift** | ⏳ | Version + migration — pin down #5 |
| **Versionable cards/templates** | ⏳ | Convention + alias mechanism — pin down #2, #3 |

---

## Recommended next-session focus

Pin-down #1 (`RenderContext`) is now resolved. The remaining "free now, expensive later" decisions:

1. **Pin-down #2 — card-id namespacing.** Agree on `<team>:<card>` IDs (e.g. `finance:revenue_trend`) + `CARD_META["aliases"]: list[str]` for renames *before* any card ID gets baked into a saved layout. Includes migrating the demo IDs and adding alias resolution in `CardRegistry`. ~1 hour.
2. **Pin-down #5 — layout-state versioning.** Stamp `{"version": 1, "layout": [...]}` into `localStorage` and add a migration hook in `_packing.py` restore. Cheap to add now, brittle to retrofit once user layouts exist in the wild.
3. **Pin-down #7 — package-import isolation.** Wrap each `CardRegistry.load_packages` import in try/except so a broken team renders a "broken team" placeholder instead of crashing startup. One-level-up of the existing per-card error boundary.

Then ship something visible:

4. **M3 — card actions plumbing.** Standard handlers for Refresh / Open-in-team-app / About declared via `CARD_META["actions"]`. Small, high-leverage for card authors. A `Card.render_settings()` settings drawer fits naturally as a fourth standard action.

Defer M4 (`dash-fn-form` swap), M5 (auth/logging/caching), M5.5 (Mantine port), M6 (MkDocs) until the cockpit is deployed in anger. Premature investment there is a recipe for rewriting good infrastructure for fictional needs — and M5.5 in particular wants the API to stop moving first.
