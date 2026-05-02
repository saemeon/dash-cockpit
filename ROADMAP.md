# dash-cockpit — Roadmap & Architecture Outlook

This document is an honest picture of where the cockpit stands, what's still rough, and what we should build (or pin down) next. It complements `CLAUDE.md` (which is the design reference) by adding an explicit forward-looking plan.

---

## Where we are today

**Shipped:**

- Cards-first protocol (`Card`, `CardMeta`) with runtime-checkable contract.
- Multi-team registry (`CardRegistry.load_packages`) with startup-time validation.
- Three page types (`TeamPage`, `UserPage`, `ConfiguratorPage`) — different access patterns, same card primitive.
- Per-card error isolation (`error_boundary`).
- Drag/resize layout via `dash-snap-grid`, with localStorage persistence (per browser, per page).
- Per-card widget sizing through `CardMeta.size`.
- Per-card menus via `CardMeta.actions` — pattern-matching events emitted on click.
- Runtime composition via `CardTemplate` + `ConfiguratorPage`, including:
  - Multi-select fan-out (one card per scalar value, cartesian product across multi-selects).
  - Cascading dropdowns via `ParameterSpec.options_fn`.
  - Idempotent Add via deterministic `card_id_for(template_id, params)`.
- Export pipeline with three opt-in protocols (`TabularCard`, `DocumentCard`, `ChartCard`) and a generic `ExportBackend`.
- Decoupled layout layer: `_packing.py` is the only module that knows about the grid engine; swapping engines means rewriting one file.
- **Tier 1 polish (from RESEARCH_NOTES):** edit-mode toggle (cards locked by default), per-card auto-refresh wired through `CARD_META["refresh_interval"]`, `dcc.Loading` spinner around every card body, `CARD_NO_DRAG_CLASS` exposed for card authors, configurable `resize_handles` on `pack_grid`.
- **Preset library (M1) — generic group model:** `Preset(name, group, entries, ...)` with opaque-string `group` namespacing. `PresetStore` protocol with `(group, name)` composite-key load/delete. Two implementations: `InMemoryPresetStore` (no filtering) and `LocalFilePresetStore` (per-group subdirs, atomic writes, three optional callable providers for visibility/writability/save-target with env-var-based defaults reading `$COCKPIT_USER`). `CockpitApp(preset_store=...)` adds a Load/Save preset section to every `ConfiguratorPage` sidebar; picker labels show `"group / name"`. Seed presets are read-only and respect group visibility. (Layout snapshotting and delete UI deferred to Phase 5.)

**Tested:** 143 tests, 76% coverage. Pure helpers, store CRUD with group filtering, env-var defaults, rendered component trees, callback registration are covered. Live Dash callback bodies (configurator, layout persistence, edit-mode apply, refresh re-render, preset load/save) are smoke-tested only.

---

## Future direction — milestones in priority order

### M1 — Saved presets ("Bibliothek") — ✅ shipped (v2 — generic groups)

A user assembles a working list in the configurator and wants to share or reload it. Today that state lives only in the browser's session store.

**Shipped (v2 — generic group model):**

- `Preset` dataclass (`name`, `group`, `entries`, `layout`, `description`, `metadata`) — JSON round-trippable. `group` is an opaque string namespace; `(group, name)` is the composite key.
- `PresetStore` protocol with `list_presets` / `save(preset)` / `load(group, name)` / `delete(group, name)`. UI never touches storage directly. Implementations enforce group-based access control and raise `PermissionError` on violations.
- The framework prescribes no group taxonomy. Conventions like `"global"`, `"team:finance"`, `"user:alice"` are deployment-defined.
- Two implementations: `InMemoryPresetStore` (no group filtering, for tests/demos), `LocalFilePresetStore` (one JSON file per preset under `<dir>/<group>/<name>.json`, atomic writes).
- `LocalFilePresetStore` accepts three optional callable providers — `visible_groups_provider`, `writable_groups_provider`, `default_save_group_provider` — invoked per operation so they can read request-scoped state (e.g. `flask.g.user_id`).
- Defaults are env-var-based: read `$COCKPIT_USER`, derive `["global", f"user:{u}"]` visible / `[f"user:{u}"]` writable / `f"user:{u}"` save target. Configurable via `user_env_var=`. With no env user, only `"global"` is visible and saves are disabled.
- Seed presets are in-memory, layered on top of disk presets, filtered by visibility, and immutable.
- Group names are sanitised against path traversal.
- `CockpitApp(preset_store=...)` adds a Load/Save section to every `ConfiguratorPage` sidebar. Picker labels show `"group / name"`. Save modal shows the destination group as a read-only line; the Save button is disabled when no group is writable.

**Deferred:** layout snapshotting in presets (`Preset.layout` exists but the save callback only stores `entries`); delete UI (protocol supports it, no button yet). Picked up in Phase 5 / M3+.

### M1.5 — URL routing & shareable views

Today the URL contributes nothing to cockpit state. Pages are addressed by integer index (`/0`, `/1`, …), and there is no way to share or deep-link a configurator working list. Two related gaps:

1. **Page URLs are unstable.** Adding or reordering pages in `CockpitApp(pages=[...])` shifts every existing link. Bookmarks and team-shared URLs break silently.
2. **Configurator state is not shareable.** A colleague who builds a useful working list can show it on their screen but cannot send it to anyone — presets close this gap *within* a deployment, but only for users who also have the named preset visible.

This milestone fixes both with one minimal addition: id-based page routing + a `_share.py` module that handles two URL params (`?b=<base64>` for ad-hoc inline bundles, `?preset=<group>/<name>` for deep-links into the existing preset store). Bundles and presets stay separate concerns: the bundle codec defines the *wire format*; the preset store defines *named persistence*. The URL hydrator dispatches between the two.

**Decisions already made (in conversation):**

- **URL = initial state, not live binding.** Layout edits and working-list mutations stay in browser stores. Editing a card after URL hydration does not push back into the URL. "Share current state" is an explicit action (Share button), not implicit on every change. This avoids fighting the existing localStorage/session-store persistence.
- **Bundle data shape = configurator working list shape.** A bundle is `list[{"template_id": str, "params": dict}]` — identical to `WORKING_LIST_STORE_ID.data` and to `Preset.entries`. No new dataclass. Both URL paths produce the same shape; the configurator hydrator is shape-only and does not know whether a bundle came from base64 or from a preset name.
- **Named bundles reuse the existing `PresetStore`.** "Named bundle" and "preset" are the same concept; the URL exposes the `(group, name)` composite key as `?preset=<group>/<name>` (and `?preset=<name>` as shorthand for `group=""`). No parallel storage abstraction.
- **Page id-based routing replaces int-index.** `?page=…` is not a separate query param — the page lives in `pathname` (`/finance-overview`). Search params are reserved for configurator state.

**URL schema:**

```
/<page-slug>                              # any page; falls back to first page on miss
/<page-slug>?b=<base64-json>              # ConfiguratorPage with inline ad-hoc working list
/<page-slug>?preset=<group>/<name>        # ConfiguratorPage seeded from named preset
/<page-slug>?preset=<name>                # shorthand: equivalent to group=""
```

`?b` and `?preset` only have meaning on a `ConfiguratorPage`; on other page types they are ignored silently. If both are present, `?b` wins (ad-hoc payload is more specific than a name reference). The `?preset` value is parsed by splitting on the **first** `/` only — preset names containing further `/` characters are preserved literally in the `name` part.

#### Sub-task A — Page id-based routing

**Files touched:** [_page.py](dash-cockpit/src/dash_cockpit/_page.py), [_app.py](dash-cockpit/src/dash_cockpit/_app.py).

- Add an optional `id: str = ""` field to `TeamPage`, `UserPage`, `ConfiguratorPage`. Default empty so existing call sites stay valid.
- New helper `_page_slug(page) -> str` in [_app.py](dash-cockpit/src/dash_cockpit/_app.py): returns `page.id` if non-empty, else `slugify(page.name)`. Slugifier: lowercase, replace any non-`[a-z0-9]` run with `-`, strip leading/trailing `-`, collapse double `-`. Empty result raises `ValueError` at startup (page name produced an empty slug — author must set `id` explicitly).
- In `CockpitApp.__init__`, build `self._pages_by_slug: dict[str, Page]`. **Validate uniqueness** — duplicate slugs raise `ValueError("Duplicate page slug 'foo' (from pages 'X' and 'Y'); set page.id explicitly to disambiguate")`. This is governance, not silent overwrite, matching the registry's startup-time validation pattern.
- `_nav_link(page)` becomes `_nav_link(page, slug)` and uses `href=f"/{slug}"`.
- `_resolve_page(pathname)` — strip leading `/`, dict lookup. On miss or empty, return first page (preserves current behaviour for `/`). Drop the `int()` parsing entirely.
- Existing callers of `_resolve_page` ([_app.py:287, 333](dash-cockpit/src/dash_cockpit/_app.py#L287)) keep working — they pass `pathname` through unchanged.

**Tests** — extend [tests/dash_cockpit/test_app.py](dash-cockpit/tests/dash_cockpit/test_app.py):

- `_resolve_page("/finance-overview")` returns the right page among multiple.
- `_resolve_page("/")`, `_resolve_page("")`, `_resolve_page(None)`, `_resolve_page("/unknown")` all return the first page.
- Building `CockpitApp` with two pages whose names slugify identically raises `ValueError`.
- A page with explicit `id="custom-slug"` is reachable at `/custom-slug` even if its `name` would slugify differently.

#### Sub-task B — Share codec module

**New file:** `src/dash_cockpit/_share.py`. Pure functions, only stdlib + the existing `Preset` import.

```python
from typing import Any, Callable, TypedDict
from urllib.parse import parse_qs

class BundleEntry(TypedDict):
    template_id: str
    params: dict[str, Any]

Bundle = list[BundleEntry]

def encode_bundle(working: list[dict]) -> str: ...
    # JSON dumps with sort_keys=True, utf-8, urlsafe-b64, strip "=" padding.

def decode_bundle(token: str) -> Bundle | None: ...
    # Pad token back to multiple of 4, urlsafe-b64 decode, JSON load,
    # validate via _validate_bundle. Return None on any error — never raise.

def _validate_bundle(raw: Any) -> Bundle | None: ...
    # Must be a list. Each entry must be a dict with str template_id
    # and dict params. Anything else: None.

def resolve_from_search(
    search: str,
    preset_loader: Callable[[str, str], Bundle | None] | None,
) -> Bundle | None: ...
    # parse_qs(search.lstrip("?")). Order: ?b first, then ?preset.
    # If ?b present and decodes: return it.
    # Else if ?preset present and preset_loader given:
    #   group, _, name = raw.partition("/")
    #   if not name: name, group = group, ""    # bare ?preset=foo → ("", "foo")
    #   try loader(group, name); on KeyError, PermissionError, or None: return None.
    # Else None.
```

**Note on the preset value grammar.** `str.partition("/")` (not `split("/", 1)`) keeps the parsing tolerant: `"foo"` → `("", "foo")`, `"team:finance/q3"` → `("team:finance", "q3")`, `"a/b/c"` → `("a", "b/c")`. The grammar is intentionally lenient — group and name strings are opaque to `_share.py`; ill-formed values become `KeyError` at the loader, not parse errors here.

Notes on the codec:

- **Sorted keys + canonical params** before JSON-encoding so the same working list always produces the same token (useful for cache/share-link equality).
- **No padding in URL tokens** (`b64encode(...).rstrip(b"=")`); decoder re-pads. This shortens shareable URLs.
- **No size limit enforced in the codec** — the browser's URL length limit is the bound. Add a soft warning in the Share button (see Sub-task D) when the encoded length exceeds ~2000 chars; presets are the recommended path for large bundles.

`_share.py` stays storage-agnostic by design — it only knows about a `Callable`. The adapter that bridges to `PresetStore` is built inline at the URL-hydrator registration site (sub-task C); no top-level helper in `_app.py`. M1 already plumbs `preset_store: PresetStore | None` through `CockpitApp` → `render_configurator` → `register_configurator_callbacks`, so the wiring exists.

**Tests** — new file `tests/dash_cockpit/test_share.py`:

- `decode_bundle(encode_bundle(x)) == x` for empty list, single entry, multi-entry with nested params.
- `decode_bundle("not-base64!!")` → `None`.
- `decode_bundle(b64("not json"))` → `None`.
- `decode_bundle(b64('{"not": "a list"}'))` → `None`.
- `decode_bundle(b64('[{"template_id": "x"}]'))` → `None` (missing `params`).
- `resolve_from_search("?b=<token>", loader)` returns the inline bundle, never calls loader.
- `resolve_from_search("?preset=foo", loader)` calls `loader("", "foo")` (bare name → empty group).
- `resolve_from_search("?preset=team:finance/q3", loader)` calls `loader("team:finance", "q3")`.
- `resolve_from_search("?preset=a/b/c", loader)` calls `loader("a", "b/c")` (first `/` only).
- `resolve_from_search("?b=<token>&preset=foo", loader)` returns inline (b wins), loader not called.
- `resolve_from_search("?preset=missing", lambda g, n: None)` returns `None`.
- Loader raising `KeyError` or `PermissionError` → `resolve_from_search` returns `None` (no exception leaks out).
- `resolve_from_search("?preset=foo", None)` returns `None` (no store wired).
- `resolve_from_search("", loader)` returns `None`.

#### Sub-task C — URL hydration callback

**Files touched:** [_configurator.py](dash-cockpit/src/dash_cockpit/_configurator.py) only. **No change to [_app.py](dash-cockpit/src/dash_cockpit/_app.py).** M1 already passes `preset_store: PresetStore | None` into `register_configurator_callbacks`; we reuse it.

Inside `register_configurator_callbacks`, build the loader closure inline next to the existing callback registrations and register one additional callback alongside the three already there:

```python
def _load_preset_entries(name: str) -> list[dict] | None:
    if preset_store is None:
        return None
    try:
        return preset_store.load(name).entries
    except KeyError:
        return None

@app.callback(
    Output(WORKING_LIST_STORE_ID, "data", allow_duplicate=True),
    Output(STATUS_ID, "children", allow_duplicate=True),
    Input("_cockpit_url", "search"),
    State(WORKING_LIST_STORE_ID, "data"),
    prevent_initial_call="initial_duplicate",
)
def _hydrate_from_url(search, current):
    bundle = resolve_from_search(search or "", _load_preset_entries)
    if bundle is None:
        return no_update, no_update
    if current:                              # don't trample user edits
        return no_update, no_update
    return bundle, f"Loaded {len(bundle)} card(s) from URL."
```

**Critical semantics — only seed an empty working list.** Once the user has edited (length > 0), navigating back to the same URL is a no-op. This matches "URL = initial state, not live binding." The `dcc.Store(storage_type="session")` keeps the edited working list across in-tab navigation.

**`allow_duplicate=True`** is required because the working-list store now has *three* writers: `_mutate_working` ([_configurator.py](dash-cockpit/src/dash_cockpit/_configurator.py)), `_load_preset` ([_presets.py:550](dash-cockpit/src/dash_cockpit/_presets.py#L550)), and our new `_hydrate_from_url`. The first two already use `allow_duplicate=True`; the third must too. `prevent_initial_call="initial_duplicate"` lets the callback fire on first render so a fresh `/configurator?b=...` visit hydrates immediately.

**Status output target — `STATUS_ID`, not `PRESET_STATUS_ID`.** The cockpit now has two status fields: the always-present configurator status (`STATUS_ID` at [_configurator.py:51](dash-cockpit/src/dash_cockpit/_configurator.py#L51)) and the preset-section status (`PRESET_STATUS_ID` at [_presets.py:388](dash-cockpit/src/dash_cockpit/_presets.py#L388)) which only renders when `preset_store is not None`. Routing URL-hydration messages to `STATUS_ID` keeps `?b=…` deep-links functional in deployments without a preset store.

#### Sub-task D — Share button (configurator sidebar)

**File touched:** [_configurator.py](dash-cockpit/src/dash_cockpit/_configurator.py).

Add a "Share link" button next to Add/Clear in the configurator sidebar. A clientside callback is the cleanest fit — duplicating the JSON+base64 logic in ~10 lines of JS avoids a server roundtrip just to read a session store. Pseudocode:

```javascript
function (n_clicks, working) {
    if (!n_clicks) return [window.dash_clientside.no_update, ""];
    const json = JSON.stringify(working || []);
    const b64 = btoa(unescape(encodeURIComponent(json)))
                  .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const url = `${location.origin}${location.pathname}?b=${b64}`;
    navigator.clipboard.writeText(url);
    const note = b64.length > 2000 ? " (long URL — consider a preset)" : "";
    return [window.dash_clientside.no_update, `Copied${note}`];
}
```

Server-side `encode_bundle` stays the source of truth (used by tests and any future export feature); the clientside variant must be byte-equivalent for round-trip with `decode_bundle`. Add a round-trip test in Python that asserts the JS-style encoding (sorted keys, no padding, urlsafe alphabet) decodes correctly via `decode_bundle`.

#### Sub-task E — Documentation

- Update [CLAUDE.md](dash-cockpit/CLAUDE.md) "Implementation status" — add a Phase 4.5 entry mirroring this milestone.
- Add a "URL schema" section to [README.md](dash-cockpit/README.md) showing the three URL forms and a `CockpitApp(preset_store=...)` example demonstrating that `?preset=` deep-links resolve through the same store as the sidebar Load button.
- Note in the team contract section: cards/templates referenced by an inline `?b=...` bundle that don't exist in the receiving deployment render an error tile via the existing per-card error boundary — no special handling needed, but worth calling out so users understand cross-deployment links can degrade gracefully.

#### Edge cases & explicit non-goals

- **`?b=` bundle references a template not in this registry.** The existing `instantiate_working_list` path renders an error tile per missing template. Acceptable — matches the per-card failure model.
- **`?preset=` references a preset not in this store.** Hydrator returns `None`, working list stays empty, no status message. Don't surface a scary error — a missing preset is functionally identical to "no URL bundle at all".
- **User opens a `?b=...` URL while already having an edited working list.** Hydrator skips (empty-only seeding). The existing URL is "consumed" only on a fresh tab/session. This is intentional; loud-overwrite UX would need a confirmation modal which is out of scope.
- **Layout snapshot in URL:** explicitly out of scope. Layouts stay in localStorage. Adding layout to bundles is M1 follow-up work (preset layout snapshotting), not this milestone.
- **Writing the URL back from edits:** explicitly out of scope. Share is an explicit button, not an implicit behaviour. Avoids spamming history and conflicting with localStorage layout state.
- **`?b=` on `TeamPage` or `UserPage`:** ignored (no `WORKING_LIST_STORE_ID` exists on those pages). The hydration callback only registers when there's a `ConfiguratorPage`, so the URL param is silently inert elsewhere.

#### Order of work

1. **`_share.py` + tests.** Pure module, no Dash, isolated. Land first — derisks the codec.
2. **Page slug migration** ([_page.py](dash-cockpit/src/dash_cockpit/_page.py), [_app.py](dash-cockpit/src/dash_cockpit/_app.py)) + tests. Independent of bundles. Ships a small but visible UX improvement on its own.
3. **Wire `preset_loader`** through `CockpitApp` → `register_configurator_callbacks`. Plumbing only, no behaviour change yet.
4. **Add the URL hydration callback** in `_configurator.py`. End-to-end working with `?b=...` and `?preset=...`.
5. **Share button** + clientside encode. Closes the user-facing loop.
6. **Docs.**

Each step lands with passing tests before moving to the next. Steps 1–2 can be PR'd independently.

**Scope:** ~120–180 lines new code + tests, one new module (`_share.py`), no breaking changes to public API (page `id` is additive, `preset_store` already exists). Page slug migration changes the URL surface — bookmarks under `/0`, `/1` stop working. Worth calling out in release notes; mitigated by URL-miss falling back to first page rather than 404.

### M2 — Per-card refresh

`CardMeta.refresh_interval` is documented but not wired. The natural pattern:

- One global `dcc.Interval(id="_cockpit_tick")` running at 1 Hz.
- A clientside callback that, on each tick, checks each card's `data-refresh-at` HTML attribute against `Date.now()` and if elapsed, dispatches a re-render.
- Cards opt out by setting `refresh_interval = 0` (current default).

**Why second:** reliability — without auto-refresh the cockpit displays stale numbers, which erodes trust faster than any other class of bug.

**Scope:** ~50 lines, one clientside callback added to `register_layout_callbacks` (or a sibling).

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

### M5 — Card groups (constrained interaction)

Cards must be independent today — that's a feature, not a bug. But there are real cases where three cards that "belong together" need shared state (e.g. a date picker that drives two charts).

**Two options, both viable:**

1. **Composite cards.** A team ships a single card whose render returns three sub-renders. State stays inside the card. Pros: zero new framework. Cons: doesn't show up as three widgets in the iOS analogy.
2. **`CardGroup` page type.** A new page type that introduces explicit group state (one shared `dcc.Store` per group). Pros: matches the user mental model. Cons: punches a hole in the "no cross-card state" rule.

**Recommendation:** try #1 first (zero framework cost). Adopt #2 only if multiple teams ask for it independently.

### M6 — Deployment & operational story

Today the cockpit is an in-process Dash app. For real corporate deployment we need:

- **Auth integration**: SAML/OIDC at the Flask level. Per-page or per-card visibility based on user attributes (`team`, `role`).
- **Logging**: structured per-card logs with team tag for routing. A failed `revenue_card` should page the finance on-call, not platform.
- **Caching**: a per-card response cache (key: `(card_id, context)`, TTL: `refresh_interval`). Without this, every navigation re-fetches.
- **Health endpoint**: `/healthz` that exercises the registry but not card data fetches.

These are not deep design issues — they're "set up the boring infrastructure" tasks. Bundle into one phase (M6) when the cockpit is deployed in anger.

### M7 — Documentation & gallery

The styleguide expects:

- `docs/` MkDocs site with API reference (`mkdocstrings`) and user guide.
- `examples/` directory with `mkdocs-gallery` scripts.

We have a working demo (`examples/demo_cockpit/`) but no MkDocs setup. Add when the API stabilises (after M1–M3) so we don't rewrite docs every week.

---

## Re-evaluating CardCanvas

Earlier we decided **not** to adopt CardCanvas as our foundation. That decision still stands, but here's a sharper version of the reasoning now that we've shipped most of what CardCanvas offers:

| What CardCanvas gives | Our equivalent | Verdict |
|---|---|---|
| `Card` ABC with `render()` + `render_settings()` | `Card` Protocol with `render()`; settings via `CardMeta.actions` + team callbacks | We have a more flexible primitive. CardCanvas couples settings UI to the card class; we let teams choose. |
| Drag-drop grid (`dash-snap-grid`) | Same engine, wrapped in `_packing.py` | Identical capability, less coupling. |
| Per-card menus | `CardMeta.actions` | Ours is opt-in and pattern-matching-friendly. |
| Settings drawer | None yet — but trivially addable as a card action that opens a modal | Future M3 work. |
| Share-by-URL for one card | None yet — see M1 (`PageBundle`) | We need a different shape: bundles of cards, not single cards. |
| Auto-refresh `interval` | `CardMeta.refresh_interval` (declared, not wired) | M2. |
| Card gallery / picker | `ConfiguratorPage` | Different model — we pick from templates, not card classes. |

**Conclusion:** CardCanvas validates our design choices; almost everything it provides we now have. The gap is in three areas (settings drawer, share-by-URL bundles, auto-refresh) — all manageable within our existing primitives.

**The one thing we should learn from CardCanvas:** its `render_settings()` pattern is clean. Cards that need user-configurable runtime state (color, threshold, time window) deserve a first-class settings UI. Today, our pattern is "use a configurator template" or "drop your own form into the card". A `Card.render_settings()` optional method, opened by a built-in `⋮` "Settings" action, would close that gap with ~30 lines.

---

## What to pin down — prerequisites for "simple, pluggable, robust"

These aren't features so much as load-bearing decisions that affect everything downstream. Resolving them now prevents painful rewrites later.

### 1. The render context dict

`Card.render(self, context: dict)` — `context` is currently always `{}`. Before any team builds against it, define what it contains.

**Proposal:**

```python
class RenderContext(TypedDict):
    user: NotRequired[dict]          # auth user, set by middleware
    locale: NotRequired[str]         # "en", "de", etc.
    page_filters: NotRequired[dict]  # date range, division — page-scoped, not card-scoped
    request_id: NotRequired[str]     # for logging correlation
```

Once a team reads `context["user"]`, we cannot reshape it. Pin this **before** M1.

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
| **Pluggable auth** | ⏳ | M6 |
| **Shareable URLs (deep links)** | ⏳ | M1.5 |
| **Robust to bad cards** | ✅ | Error boundary, isolation by design. |
| **Robust to slow cards** | ❌ | Render timeout — pin down #6 |
| **Robust to bad team packages** | ⏳ | Startup try/except — pin down #7 |
| **Robust to layout schema drift** | ⏳ | Version + migration — pin down #5 |
| **Versionable cards/templates** | ⏳ | Convention + alias mechanism — pin down #2, #3 |

---

## Recommended next-session focus

1. **Pick one "pin down" item** (most leverage: #1 RenderContext shape, then #2 card identity convention). These cost nothing to decide today and a lot to change once teams build against them.
2. **Build M1 (presets)**. It's the biggest user-visible win and exercises the storage abstraction we'll need for M6 too.
3. **Then M2 (refresh)**. Reliability dividend.

Defer M4–M7 until the cockpit is deployed in anger and pain points become concrete. Premature MkDocs / dash-fn-form / auth investment is a recipe for rewriting good infrastructure for fictional needs.
