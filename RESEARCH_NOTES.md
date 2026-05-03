# Research notes — dash_snap_grid & cardcanvas

Raw incremental notes from reading both repos. Cleaned up afterwards.

Goal: figure out what we can learn, copy, or leverage.

---

## dash_snap_grid

### Surface area

Three components exposed: `Grid`, `ResponsiveGrid`, `DraggableDiv`.
We currently use `Grid` only. The other two are interesting:

- `ResponsiveGrid` — same props plus breakpoint-aware layouts (different layout per screen size).
- `DraggableDiv` — atomic draggable element. Use case: drag-from-toolbox into a `Grid` (the Grid's `isDroppable` accepts dropped DraggableDivs).

### Grid props we don't yet use

Significant ones we're leaving on the table:

- **`allowOverlap=False` (default)** — could enable for "free-form" pages
  if anyone wants Bloomberg-style stacked cards. Probably keep off.
- **`isDroppable=True` + `droppedItem`** — *this is the killer prop*. Combined
  with `DraggableDiv`, we get drag-from-toolbox: the user picks a card from a
  side gallery and drags it onto the page. This is how CardCanvas's "card picker"
  works under the hood. See M5 / "card gallery" thinking.
- **`preventCollision`** — could be useful for "pinned" cards that don't
  reorganise when neighbours move. Niche.
- **`resizeHandles=['se']` (default)** — only south-east corner. Could expose
  this so users can resize from any edge: `['s','w','e','n','se','ne','sw','nw']`.
  Minor UX upgrade.
- **`useCSSTransforms=True` (default)** — already set, gives 6× faster paint
  during drag. Good — keep.
- **`transformScale`** — parent-CSS-scale-aware drag. Useful if cockpit ever
  embedded inside a scaled viewport (e.g. presentation mode). Low priority.

### Things we already use well

- `compactType="vertical"` — auto-pack upward when cards are removed.
- `draggableCancel` — exclude inputs/buttons from drag-start trigger.
- Pattern-matching ids on `Grid` (we wrap with `{"type": ..., "key": MATCH}`)
  — this works because the Grid has `id` as a string OR dict, and Dash
  pattern-matching machinery doesn't care.

### ResponsiveGrid — what we're missing

`ResponsiveGrid` is just `Grid` with breakpoint awareness. Key differences:

- `cols` becomes a dict `{lg: 12, md: 10, sm: 6, xs: 4, xxs: 2}` — different
  column count per screen size.
- `layouts` is a dict `{breakpoint: [layout_items]}` — different layout per
  breakpoint. Each one persists independently.
- `breakpoints` defines pixel cutoffs for the size classes.
- `breakpoint` and `col` are *output* props — read by callbacks to know what's
  active.

**Implication for cockpit:** if we want mobile-friendly layouts, we should use
`ResponsiveGrid` instead of `Grid`. Same code path; the layout dict shape is
the only thing that differs. The `_packing.py` decoupling makes this a
1-file swap.

Practical concern: most executive cockpits are desktop-only. Hold off
unless mobile becomes a real requirement.

### Pattern: layout state is bidirectional

`Grid.layout` is *both* an Input and an Output:

- User drags → React updates `layout` → Dash callback can read it.
- Server sets `layout` → React renders new positions.

This is what makes our save/restore work with one pair of pattern-matching
callbacks. Worth knowing for future engine swaps: any replacement must
support this bidirectional flow, otherwise persistence becomes painful.

### Drag-and-drop pattern (example 07)

The drag-from-toolbox flow is dead simple:

1. Wrap palette items in `DraggableDiv(component, id="drag-foo")`.
2. Set `Grid(isDroppable=True)`.
3. On drop, Grid emits `droppedItem = {"i": ..., "x": ..., "y": ..., "w": ..., "h": ...}`.
4. Server callback reads `droppedItem`, decides what card to instantiate based
   on the source `id`, appends to `children` + `layout`.

**Adoption recommendation:** this is exactly what we want for an
"add card" UX on `TeamPage` — let the user drag from a sidebar gallery
into the grid. Replaces the "configurator picker → fill form → click Add"
flow for the simple case where the card has no parameters.

Implementation cost: ~80 lines. New module `_palette.py` with:
- `render_palette(card_ids, registry)` — returns a column of `DraggableDiv`s.
- A pattern-matching callback that handles `droppedItem` and inserts into
  the page's grid.

This is **clearly a Phase-4 candidate** — bigger UX win than the configurator
for the common case.

### Toolbox / close-button pattern (example 06)

Cards inside the grid get an **X close button** with the `no-drag` class so
clicking close doesn't trigger drag. Removed cards re-appear in a "toolbox"
strip above the grid; clicking adds them back.

**Adoption:** matches our `⋮ → Remove` action. Their version is more visible
(always-on X) but uglier. Ours is better as a default, but theirs is faster
when iterating layouts. Could be a CSS toggle: "edit mode" turns on always-on
remove handles.

### Save/load layout pattern (example 05)

Two-button approach: "Save" copies grid layout into a Store; "Load" copies
Store back into grid. We do this transparently with auto-save on every change
and auto-restore on hydrate. Theirs is more explicit (button-driven), which
is **less magical** and might be better UX for users who don't expect their
casual drag to persist.

**Adoption:** add an explicit "Reset layout" button per page (rather than
having to clear localStorage). Trivial: dispatch the page's initial layout
back to the Grid output.

### What we should adopt

**Direct copies (small wins):**

- Configurable `resizeHandles` — default `['se']` is one corner; we can let
  users resize from any edge with no code change other than the prop.
- An explicit "Reset layout" affordance per page — see save/load notes above.
- Document the `useCSSTransforms=True` setting; it's a real perf win during
  drag of 20+ cards.

**Larger adoptions (Phase 4–5):**

- **Drag-from-palette flow** (M5 in roadmap, but bumped). Use `DraggableDiv`
  + `Grid(isDroppable=True)`. New module `_palette.py`. Significant UX win.
- **ResponsiveGrid swap** if mobile becomes a requirement. Engine swap
  + initial layouts need to be expressed per breakpoint.
- **Edit mode toggle** — show always-on remove/resize handles when the user
  hits "Edit page". Mirrors how iOS widgets get jiggly when you hold-press.
  Would replace our hidden ⋮ menu in places where it's not obvious.

---

## CardCanvas

### Surface area

Three exports: `CardCanvas` (the app), `Card` (the ABC), `CardManager`
(registry-equivalent), `GlobalSettings` (page-level settings ABC).

### Card class — what they do differently from us

Their `Card`:

- **Class-based, not protocol-based.** Uses `ABC` with `@abstractmethod render`.
- **Carries class attributes for the picker UI**: `title`, `description`,
  `icon`, `color`. We carry these in `CARD_META`. Equivalent.
- **Has `interval` and `grid_settings`** as class attributes — equivalent to
  our `refresh_interval` and `size`. Same idea, different shape.
- **`debug` flag** turns on full traceback render. We always render the
  exception message; full traceback is only useful for devs. Worth copying
  as an opt-in.
- **`render_container()` is the canonical wrapper**: places menu, loading
  spinner, Interval, error rendering, position/height styling. Our
  equivalent is split across `_layout.py + _refresh.py + _packing.py +
  _configurator.py:_render_card_tile`. Theirs is more centralised.

### Card menu — what it includes

Standard ⋮ menu items per card (always present, not opt-in like ours):

- **Settings** — opens a drawer with `card.render_settings()` — full per-card
  settings UI. Cards declare what controls go in the drawer.
- **Duplicate** — clones the card (settings + position).
- **Share Link** — encodes the card's settings + layout into a URL query
  param.
- **Delete** — removes from the canvas.

**Insight:** these four are the *generic* card actions. We could ship them
as defaults instead of starting from "no actions, opt in via `CARD_META`".

Our model is: cards opt in to actions explicitly. Their model: cards inherit
generic actions and may add more. Their model is more discoverable but less
flexible.

**Possible adoption:** add a few default actions (Refresh, About, Open in
team app) that all cards get for free, with `CARD_META["hide_default_actions"]`
to opt out. Then `actions` adds custom ones on top.

### `dcc.Loading` overlay

Their card wrapper wraps render output in `dcc.Loading` so a slow render
shows a spinner. We don't do this. Cheap UX win — copy it.

### Settings drawer pattern (the big one)

Their `render_settings()` returns a Dash component with input controls.
Each control's id follows:
`{"type": "card-settings", "id": self.id, "setting": "<setting_name>"}`.

A pattern-matching callback bundles all settings inputs back into the
card's settings dict, which gets stored globally and re-passed on render.

This is **strictly more powerful** than our `CARD_META["actions"]` opt-in
menu. Our actions emit events; theirs emit *state changes* that re-render
the card with new settings.

**Adoption proposal:** add an optional `Card.render_settings(self) -> Component`
method. If present, the cockpit:

1. Adds a "Settings" item to the ⋮ menu.
2. On click, opens a modal containing `card.render_settings()`.
3. Setting controls write to a per-card session store
   (`{"type": "_cockpit_card_settings", "card_id": cid}`).
4. The card's `render(context)` receives the settings via `context["settings"]`.

This is genuinely useful — e.g. a "Top N table" card that lets the user pick N.

**Caveat:** breaks our "cards are stateless renders of `(context)`" model.
Settings *are* state. But it's per-card-and-per-user, not cross-card, so
the iOS widget analogy still holds (widgets have settings too).

### `GlobalSettings` — page-level state

Cards receive `global_settings` alongside their own settings. This is how
they implement "page filters" (date range, division, etc. that affect
multiple cards). We have `RenderContext.page_filters` *as a planned shape*
but no implementation yet.

**Adoption:** their `GlobalSettings` ABC is one way. Or we put global
settings in the `RenderContext` directly with no class hierarchy. Same
end result. Their version is heavier; ours could be lighter if we just
pass it through `context`.

### State model — multi-store with event dispatch

CardCanvas runs **five** stores in parallel:

| Store | Storage | Purpose |
|---|---|---|
| `cardcanvas-main-store` | local | Persistent saved state (cards + layouts + settings). Updated only on explicit Save click. |
| `cardcanvas-config-store` | memory | Current card config (which cards exist, with what settings). |
| `cardcanvas-layout-store` | memory | Current layouts (positions per breakpoint). |
| `cardcanvas-global-store` | memory | Current global settings dict. |
| `cardcanvas-event-store` | memory | Event bus — `{"type": "add-card"|"delete-card"|"update-card"|"re-render", "data": ...}`. Many actions write events here; one big callback dispatches. |

**Insight 1 — the event-store pattern.** Instead of N direct paths from
N actions to the grid, they have N→1 (write event) and 1→1 (dispatch).
This is *exactly* the redux pattern in a Dash store. Dramatically reduces
callback count and makes "what changed and why" inspectable in one place.

**We could adopt this** if our callback graph grows. Today it's small enough
that direct callbacks are fine. But once we add presets/duplication/share-by-URL,
the event-store pattern saves complexity.

**Insight 2 — explicit Save vs automatic.** They require a "Save Layout"
button click to persist. Ours auto-saves on every drag. Their model:

- Pros: user-controlled. No fear of accidental change. Reset button reverts
  to last save.
- Cons: easy to forget; close the tab and lose work.

Ours: opposite tradeoffs.

**Possible compromise:** auto-save to a transient localStorage key, but
also expose an explicit "Save" button that copies current state to a
named bundle (M1 in roadmap).

### Edit mode toggle (genuine win)

`toggle_edit_mode` flips:

- `isDraggable=True/False` on the grid.
- `isResizable=True/False` on the grid.
- `display=block/none` on every card menu.

Non-edit mode → cards locked, menus hidden, view-only experience.
Edit mode → handles + menus visible, drag enabled.

**Adoption is straightforward** for us: one new button, one callback that
flips three things. Better UX than always-on drag (which we have today)
because executives won't accidentally rearrange their dashboard.

### Card actions (their built-in 4)

Per-card menu has four entries always present:

1. **Settings** → opens drawer with `card.render_settings()`.
2. **Duplicate** → clones the card with a new uuid, copies settings + layout.
3. **Share Link** → encodes card+layout+settings into URL query param
   (base64 + JSON), opens in shared mode with chrome hidden.
4. **Delete** → removes from canvas.

Compare to ours:
- Our `⋮` shows only `Remove` (in configurator) or whatever the card
  declares in `actions`.
- Settings: not implemented.
- Duplicate: not implemented (templates instantiate; no clone of an
  existing card with same params).
- Share Link: not implemented.

**Adoption priority:**
- Settings (high — enables a class of dynamic cards we can't currently support).
- Duplicate (medium — useful for templates).
- Share Link (medium — needs M1 first).
- Delete: we have it.

### Share-by-URL implementation

`_build_card_share_payload`:

```python
{
    "v": 1,                           # version key (great practice)
    "card_id": "abc-uuid",
    "card": {
        "card_class": "RevenueCard",
        "settings": {...},
    },
    "layouts": {
        "lg": [{i, x, y, w, h}],
        ...
    },
    "global_settings": {...},
}
```

URL-safe via `urlencode + json.dumps(separators=...)`. Loaded back via
`?ccs={...}` query param. **Versioned** so future format changes can
migrate (very nice — copy this).

**Constraints worth knowing:**

- Browsers limit URL length (~2000 chars practical, 4096 max). Card
  with large settings might overflow. They don't compress; we should
  consider gzip+base64.
- Deep-linking to one card means the shared URL omits other cards.
  Different from sharing a whole page; both have valid use cases.

### Per-card refresh

Their version (lines 946–961):

```python
@app.callback(
    Output({"type": "card-content", "index": MATCH}, "children"),
    Input({"type": "card-interval", "index": MATCH}, "n_intervals"),
    State("cardcanvas-config-store", "data"),
    State("cardcanvas-global-store", "data"),
    prevent_initial_call=True,
)
def update_card(n_intervals, cards_config, global_settings):
    ...
    card = card_objects[card_id]
    return card.render()
```

Same shape as our just-shipped `register_refresh_callbacks`. Differences:

- They re-instantiate the card from settings + global_settings on every tick.
  We re-render the same registered card object.
- They include `settings` in the re-render — so if user updated settings,
  next tick uses new settings.

**Implication for our settings adoption:** when we add `render_settings()`,
the refresh callback needs to read the per-card settings store and pass
them in. Should design the settings model with refresh in mind.

### Loading spinner (small win)

```python
dcc.Loading(
    html.Div(id={"type": "card-content", "index": self.id}, children=card_content),
    custom_spinner=dmc.Loader(type="oval", ml="md"),
    overlay_style={"visibility": "visible", "filter": "blur(2px)"},
)
```

Wraps card body so the user sees a spinner during slow renders. **Direct
copy candidate** — wrap our `error_boundary` output in `dcc.Loading`.
~5 lines.

### Settings model (the big architectural difference)

CardCanvas's `Card` carries `self.settings` (per-card dict) and
`self.global_settings` (page-wide dict). Both injected at instantiation.
The Card's `render()` reads from `self.settings` directly.

`render_settings()` returns a form whose inputs have ids of the shape
`{"type": "card-settings", "id": self.id, "setting": "<name>"}`. A
generic callback bundles all these into a settings dict, writes to config
store, and fires a re-render event for that card.

**This is the cleanest "per-card runtime settings" model I've seen.** The
key insight: the Card class doesn't need to wire its own settings callback —
the cockpit does it generically via pattern-matching IDs.

**Adoption proposal — a minimal port:**

Add to `Card` protocol (optional):
```python
def render_settings(self) -> Component | None:
    """Return a form whose inputs use the standard pattern-matching ids."""
    return None  # default: no settings
```

Add helper:
```python
def card_setting_id(card_id: str, setting: str) -> dict:
    return {"type": "_cockpit_card_setting", "card_id": card_id, "setting": setting}
```

Add a generic callback in `_app.py` that:
1. Listens to a "Save settings" button in a settings drawer.
2. Reads all `_cockpit_card_setting` inputs for the current card.
3. Writes to `dcc.Store({"type": "_cockpit_card_settings_store", "card_id": cid})`.
4. Emits a refresh event so the card re-renders with new settings.

Cards' `render(context)` reads `context["settings"][card_id]` (or similar).

**Cost:** ~150 lines, plus the settings drawer infrastructure.
**Benefit:** unblocks "user-tunable cards" entirely. High-impact.

### Toolbar — 6 layout-management buttons

CardCanvas's `main_buttons()` ships:

- **Add Cards** — opens drawer with card gallery (drag or click + button).
- **Upload Layout** — `dcc.Upload` for JSON file → state restored.
- **Download Layout** — current state → JSON download.
- **Save Layout** — current state → localStorage.
- **Restore Layout** — back to last saved (yellow icon).
- **Reset Layout** — back to default (red icon).
- **Clear Layout** — empty everything (red icon).
- **Edit Mode toggle** — switch between view-only and editable.
- **Color Scheme toggle** — light/dark.

Most of these are mass-state operations on layouts. We currently expose
none of them.

**Adoption priority (what ours should pick up):**

1. **Edit mode toggle** — clear win, low cost. Directly addresses "executives
   shouldn't accidentally rearrange". HIGH.
2. **Reset layout** — small win. Lets users recover from bad drag.
3. **Save / Restore** — gated on whether we keep auto-save (probably skip).
4. **Download / Upload** — useful for sharing layouts as files. MEDIUM.
5. **Clear Layout** — low priority; risky.

### Card gallery (preview-style picker)

`render_card_preview(card_class)` returns a `DraggableDiv` styled as a card
preview tile. Has icon, title, description, and a "+" action icon.

User flow: click "Add Cards" → drawer opens with all card class previews →
either drag onto the grid OR click the "+" on a preview tile.

**Two paths to add (drag OR click)** is good UX — drag is fast for power
users, click is discoverable for everyone else.

**Adoption note:** for a TeamPage, every cockpit card already lives on the
page (no add/remove). For ConfiguratorPage, we have the form-driven Add
flow but no drag/click gallery. Adding the gallery would be a UX upgrade
to the configurator: instead of "pick template, fill form, click Add",
the user sees all available templates as preview tiles and drags one in
(opens the form on drop).

### Lessons from charts.py (the killer demo)

The most instructive cardcanvas example is `examples/charts.py`. It
implements 8 different "smart" chart cards — Histogram, HeatMap, Violin,
BarChart, TopNBarChart, Highlight, Markdown, Map. Each is fully
user-configurable via `render_settings()`.

**What this shows:** with the settings-drawer pattern, cards become
*tableau-like* — the user picks columns, aggregations, and filters from
a side drawer; the chart re-renders on save. No templates required, no
fixed parameters at registration time.

**The `generate_filter()` helper** (lines 145–198) is genuinely clever:
inspects a pandas Series dtype and auto-builds a filter widget (checkbox
group for categorical, range slider for numeric). The pattern:

```python
if column.dtype in ["object", "string", "bool", "category"]:
    return dmc.CheckboxGroup(...)
if column.unique().shape[0] > 100:
    return text("Too many unique values to show filter")
return dmc.RangeSlider(min=column.min(), max=column.max())
```

**Cascading filter pattern** — when the X column changes, the X filter
re-renders to match the new column's type. Implemented as a
`@callback(MATCH on x setting → MATCH on x-filter container)`. This is
the same pattern as our `options_fn` but expressed as a separate
container DIV that the callback rewrites.

**Adoption insight:** if we ship `render_settings()`, we should ship
this `generate_filter()` helper alongside. Or include it as an opt-in
import like `from dash_cockpit.helpers import auto_filter`.

### dash-mantine-components vs dash-bootstrap-components

CardCanvas uses dmc throughout. We use dbc. Differences:

- **dmc has drawers, color pickers, notifications, json input,
  range sliders, checkboxgroups, multi-select with search, etc.**
  dbc lacks several of these (drawer is hacked from offcanvas, no native
  color picker, no native notification toast).
- dmc renders prettier by default. Looks more modern (mantine-style).
- dmc has built-in dark mode.
- dbc has wider community adoption and is closer to the "Dash standard".

**Verdict:** for the cockpit's level of interactivity, dmc is materially
better. But switching is **not casual** — every component reference would
change. Probably stay on dbc for now; revisit if/when the configurator
needs a settings drawer.

### Class-vs-instance card model — architectural insight

The deepest architectural difference between cardcanvas and dash-cockpit:

- **CardCanvas:** Card classes are registered. Card *instances* are
  created on demand from per-instance settings stored in a global config
  store. Every card on a canvas has a uuid. Duplicating a card means
  creating a new uuid pointing at the same class with copied settings.
- **dash-cockpit:** Card *objects* are registered. There's a 1:1
  relationship between registry entries and rendered cards. Templates
  exist as a separate concept for parametrised cards.

Their model is **simpler for end users** (everything is a class; settings
make instances unique). Ours is **simpler for card authors** (most cards
are just objects; only parametrised ones become templates).

Both are valid. The question is: do we want `revenue_card` and
`revenue_card_with_threshold_50` to be different things (our model) or
the same class with different settings (their model)?

**Probably ours is right for the executive cockpit use case** because:
- "Official" cards (revenue, KPIs) are stable and don't need duplication.
- User-built cards are explicit (configurator).
- No accidental "two copies of the same card with slightly different
  settings" confusion.

But the architecture has a cost: **adding `render_settings()` requires
us to introduce per-card runtime state**, which we currently don't have.
Adopting their settings-drawer pattern would push us partway toward their
class-vs-instance model.

---

## Synthesis — what to actually do

Sorted by impact × cost. Each item names a concrete code change.

### Tier 1 — adopt soon (high value, contained scope) — ✅ shipped

#### 1.1 Edit mode toggle

**What:** a switch (or button) per page that flips `Grid.isDraggable` /
`isResizable` and shows/hides the per-card ⋮ menus. Default: view-only.

**Why:** executives shouldn't accidentally rearrange. Today our default
is editable; theirs is locked. Theirs is correct for the audience.

**Where:** new component in `_app.py` sidebar; one callback that updates
the active grid + menus via pattern-matching outputs.

**Cost:** ~50 lines.

#### 1.2 `dcc.Loading` wrapper around card body

**What:** wrap `error_boundary(...)` output inside `dcc.Loading` so slow
renders show a spinner.

**Why:** trust UX. Without it, a 3-second card looks frozen.

**Where:** modify `wrap_for_refresh` in `_refresh.py` (or a new helper)
to add the loading wrap.

**Cost:** ~5 lines.

#### 1.3 Document the `.no-drag` class for card authors

**What:** make our `draggableCancel="...,.card-no-drag"` selector
discoverable. Document: "any element with `className='card-no-drag'`
won't trigger drag-start when clicked."

**Why:** card authors will hit this immediately when they put a button
or input inside a card. Currently undocumented.

**Where:** README + a `dash_cockpit.cards` helper module exposing the
constant.

**Cost:** ~10 lines of code + a doc paragraph.

#### 1.4 Configurable resize handles

**What:** expose `resize_handles` on `pack_grid` (and `TeamPage`?). Default
stays `['se']`; cockpit users can opt into all 8.

**Why:** UX preference; trivial code.

**Cost:** ~5 lines.

### Tier 2 — adopt next (high value, bigger scope)

#### 2.1 `Card.render_settings()` + settings drawer

**What:** add an optional method to the `Card` protocol; cockpit renders
a settings menu item that opens a drawer with the form; saves write to a
per-card `dcc.Store`; settings flow into `context["settings"]` on next
render.

**Why:** unblocks user-tunable cards (the cardcanvas charts.py-style demo
becomes possible). Massive expansion of what cards can be without
forcing teams to write templates.

**Where:** new module `_settings.py`. New pattern-matching IDs. Drawer
component in `_app.py`. Card protocol extended (backwards-compatible).

**Cost:** ~200 lines + UI work for the drawer.

**Caveat:** introduces per-card runtime state. We need to decide:

- Per-user (browser) or per-deployment (server-side store)?
- How does "Reset to defaults" work?
- How do settings interact with refresh callbacks (settings change must
  trigger re-render)?

#### 2.2 Drag-from-palette flow

**What:** new module `_palette.py` with a render-able card gallery
(`DraggableDiv` per registered card). The gallery is a sidebar drawer
opened by an "Add" button. Drop into a `Grid(isDroppable=True)` adds the
card.

**Why:** matches the standard "build your dashboard" UX pattern. Replaces
the configurator's form-only Add flow for parameter-less cards.

**Where:** new `_palette.py`; modify `pack_grid` to set `isDroppable=True`
when palette is enabled; new pattern-matching callback for `droppedItem`.

**Cost:** ~150 lines.

#### 2.3 Versioned share-by-URL bundles (M1 in roadmap, refined)

**What:** copy cardcanvas's `_build_card_share_payload` shape — a
versioned JSON payload encoded in a URL query param. Adapt for our case:
share a *page bundle* (list of cards + layout + settings), not just one
card.

**Why:** users want to send a colleague a link to their cockpit view.
URL-based is the lowest-friction option (no server-side storage needed).

**Where:** new module `_bundles.py`. URL parser + serialiser. Drawer
to copy share link. Optional: filesystem `BundleStore` for big bundles
that exceed URL limits.

**Cost:** ~250 lines (versioning, validation, URL encoding, UI).

### Tier 3 — adopt if needed (lower value or speculative)

#### 3.1 ResponsiveGrid swap (mobile)

**What:** swap `Grid` for `ResponsiveGrid`. Layouts become per-breakpoint
dicts. Persistence keys also become per-breakpoint.

**Why:** mobile/tablet support. Uncertain if cockpit needs this.

**Where:** rewrite `pack_grid` in `_packing.py`; expand the persistence
shape; add migration for existing localStorage data.

**Cost:** ~100 lines + a non-trivial migration.

#### 3.2 Event-store dispatch pattern

**What:** introduce a single `_cockpit_event_store` that all UI actions
write to (with `{"type": ..., "data": ...}` payloads). One big callback
dispatches based on `event.type` and updates the relevant stores.

**Why:** at scale this dramatically reduces the number of callbacks and
makes dependency graphs cleaner. Today we don't have enough callbacks
to need it.

**Where:** wholesale refactor of `_app.py` and `_configurator.py`.

**Cost:** ~400 lines refactor. Defer until callback graph hurts.

#### 3.3 Move from dbc to dmc

**What:** swap dash-bootstrap-components for dash-mantine-components.

**Why:** more polish, more components (drawer, color picker,
notifications, range slider, etc.). Esp. valuable if we adopt the
settings drawer.

**Where:** every UI component reference. ~30+ files.

**Cost:** large. Defer indefinitely unless settings drawer adoption
forces the issue (drawer is dmc-native; building one in dbc is awkward).

#### 3.4 `auto_filter()` helper for column-based filters

**What:** copy cardcanvas's `generate_filter()` logic — auto-build a
filter widget from a pandas Series. Useful for "data-driven" cards.

**Why:** if/when we add `render_settings()` and want to make table-like
cards user-tunable.

**Where:** new module `dash_cockpit.helpers.filters`.

**Cost:** ~80 lines.

---

## Insights for the team contract

Things we should explicitly tell card authors based on what we learned:

1. **Stable IDs forever.** Layouts persist by `card.CARD_META["id"]`. Don't
   rename. Use the team-prefix convention to avoid collisions.
2. **Cards must fill their cell.** `height: 100%` or flex everywhere.
   Pixel heights clip or leave gaps.
3. **Use `className="card-no-drag"`** on inputs/buttons inside cards or
   they'll trigger drag-start.
4. **`refresh_interval` in seconds.** 0 = no refresh. Don't poll faster
   than your data source can tolerate.
5. **`size=(w, h)`** is in widget units (defined by the page's `columns`),
   not pixels. `(2, 1)` = 2 cols wide, 1 row tall.
6. **Cards must be self-contained.** No imports from other team cards. No
   shared state.

---

---

## Inspiration: Kennzahlenvergleich Bibliothek (R/Shiny)

The original R/Shiny app that inspired the cockpit had a "Bibliothek" pattern
worth keeping in mind as inspiration (not as a literal port).

**What they did:**

- The sidebar had two **tabs side-by-side**: `Konfigurator` (build a new
  evaluation by picking dimensions) and `Bibliothek` (pick from saved
  presets). One "Kennzahl(en) anzeigen" button reacted to whichever tab
  was active.
- The Bibliothek dropdown merged **team-curated presets** ("offizielle
  Auswertungen") and **user-saved presets** into a single list — same
  picker, no distinction in the UI.
- Saving a preset asked for a name; warned if it already existed and
  offered overwrite. Deleting a preset offered a "pick from your saved
  ones" dropdown.
- A preset was just a *list of card names* + a year. Loading it
  diff'd against the current working list and only added missing cards
  (idempotent).

**What's worth borrowing as an idea:**

- **One picker, two sources** (curated + user-saved) is cleaner than
  separate UIs.
- **Idempotent load** — loading the same preset twice doesn't duplicate
  cards.
- **Modal-driven save/delete** with name validation + overwrite
  confirmation is a reasonable UX. Doesn't need to be a custom modal —
  any drawer/dialog works.
- **The preset = list of card identifiers** model is simpler than
  serialising every layout dim. Layout positions are layered on top
  separately.

**What we should NOT replicate:**

- Their reactive plumbing (`gargoyle`, `observeEvent`, copy-reactive)
  is Shiny-specific — Dash patterns differ.
- The "datayear first, then preset" two-step pick is product-specific
  to their domain (annual data). We don't need that nesting.

**Refines M1 in ROADMAP** — the right shape for our presets is probably:

```python
@dataclass(frozen=True)
class Preset:
    name: str
    card_ids: list[str]        # which cards to instantiate
    layout: dict | None = None # optional saved positions
    metadata: dict = field(default_factory=dict)
```

Plus a `PresetStore` protocol (load/save/list/delete) so the storage
backend is pluggable: filesystem, browser localStorage, server DB,
URL-encoded — implementer's choice.

UI: one drawer or sidebar section listing all presets (curated + user
mixed), with Save/Delete buttons next to it. Mirrors but doesn't copy
their pattern.

---

## Where this fits in the roadmap

Updates to ROADMAP.md based on this research:

- **M1 (Saved presets)** → re-spec as "shareable URL bundles" using
  cardcanvas's versioned-payload shape. Filesystem/server storage becomes
  a follow-up if URL length is exceeded.
- **M3 (Card actions plumbing)** → expand to include `render_settings()`
  per Tier 2.1. This is the biggest single feature missing from our
  framework.
- **New M5b (Drag-from-palette)** → adds Tier 2.2. Promote ahead of
  speculative items.
- **M4 (dash-fn-form)** → keep as **deferred / probably skip**, we
  already concluded the spec-vs-signature mismatch makes it awkward.
- **New: M2.5 (Edit mode toggle, dcc.Loading wrap)** → small Tier 1
  improvements, stage for the next minor release.

---

## Card sizing — options for later evaluation

Captured 2026-05-03 during a UX pass on the demo. Cards felt too large; references are macOS widgets (small/medium/large/extra-large in a fine icon grid) and Bloomberg terminal (dense, many small panels).

**Shipped:** density tuning — `columns` default `2 → 4`, `DEFAULT_ROW_HEIGHT 280 → 180`. Fixed pixel rows. Cards now closer to macOS-small in feel.

**Tried and reverted (2026-05-03):** viewport-fill clientside callback that adapted `rowHeight = (viewport - margins) / total_rows`. Result was the opposite of what we wanted — pages with few rows produced cards that ballooned to fill the viewport (a `(2, 2)` card on a 2-row page took the entire screen). iOS widgets and Bloomberg panels both use **fixed pixel sizes**, not viewport-stretching. Empty space below a sparse page is honest ("there are only this many rows of content") rather than a bug to paper over. Lesson: do not stretch cards to fill; either ship more cards per page or accept the empty space.

**Subsequently shipped (same day):** square-cell clientside callback in `register_square_cell_callbacks` — `rowHeight = column_width` so every `(1, 1)` is a true square regardless of viewport. `columns` default raised `4 → 6`. `CockpitApp(content_max_width=1600)` caps the page-content area on ultra-wide monitors. macOS-widget feel achieved without viewport-stretching.

### Deferred — user-level cockpit settings panel

Right now `content_max_width`, `columns`, theme are deployment-set on `CockpitApp(...)`. Users would benefit from a per-browser settings panel (sidebar gear icon → modal) where they can override:

- Density: 4 / 6 / 8 columns (drives `columns` per page).
- Content max width: narrow / wide / unlimited.
- Theme variant: light / dark.
- Edit mode default: locked / unlocked on load.

Storage: `dcc.Store(storage_type="local")` with a settings dict. Resolution: user setting → page declaration → cockpit default. Build only when at least one team or user asks for it; keep the simple constructor kwargs as the source of truth until then.

The five options brainstormed (in order of scope):

### Option 1 — Just shrink (the path we took)

Bump default `columns` and lower the row-height floor. No API change. Ships denser visual without touching cards. Authors still write raw `(w, h)` tuples.

**Trade-off:** "what's the right column count?" is arbitrary; varies by screen size. We picked 4 as a middle ground between today's 2 and Bootstrap's 12.

### Option 2 — Named sizes (macOS-style vocabulary)

Add a small vocabulary that resolves to `(w, h)` at pack time, knowing the page's `columns`:

```python
SIZE_ALIASES = {
    "small":  (1, 1),         # smallest tile
    "wide":   (2, 1),
    "tall":   (1, 2),
    "medium": (2, 2),         # square
    "large":  (3, 2),
    "banner": ("page", 1),    # spans full row, special "page" sentinel
    "full":   ("page", 2),
}
```

Card declares `"size": "wide"` instead of `(2, 1)`. Raw tuples remain the escape hatch. ~20 lines of resolution in `_layout._card_size` and `_configurator._card_size_from_meta`.

**Why we'd pick this up:** card metadata reads like intent; vocabulary is robust to changing column counts; clearer in code review. Ship after we see whether Option 1 alone is enough.

**Risks:** vocabulary inflation (how many names is too many?); the `"page"` sentinel is a special case the resolver must handle. Pick a small set (≤ 7) and let raw tuples cover the rest.

### Option 3 — Bloomberg-style (12-col grid + free pixel resize)

Default `columns=12` (Bootstrap-grid scale), `MIN_ROW_HEIGHT=60`. Cards declare integer cell counts in a fine grid. Power users resize freely.

**Why we'd pick this up:** maximum density and shape variety; familiar to Bootstrap users.

**Why we deferred it:** higher cognitive load per card author; small text becomes hard to read inside tiny cells; fights the "card-is-a-glance" intent. Better as an opt-in per page (`TeamPage(columns=12)`) than as the default.

### Option 4 — Two-axis decoupled (Bootstrap-horizontal, coarse-vertical)

12 horizontal columns, 1–3 vertical rows only. Decouples "how wide" from "how tall" because vertical eats viewport much faster than horizontal.

**Why we'd pick this up:** generous horizontal precision, restrained vertical; matches a lot of dashboard intuition.

**Why we deferred it:** mixes two scales — another grammar to learn. Probably only worth it if Option 2's vocabulary doesn't generalise.

### Option 5 — Hybrid (Option 1 + Option 2)

Recommended end state once we've felt out the right column count. Steps:

1. Density tuning (Option 1) — done.
2. Add named-size resolver (Option 2) — pending.
3. Migrate demo cards to named sizes one at a time, A/B the vocabulary.

### What to watch for before re-evaluating

- Do real cards feel constrained by `(1, 1)` being 1/4 width × 1 row tall? If yes, denser default needed (Option 3-style).
- Do authors keep writing raw tuples and complaining? → ship Option 2.
- Do cards on different page widths look wrong? → Option 4 or responsive sizes (covered separately as the iOS-breakpoint idea, not yet on the roadmap).
- Empty grid cells (when card sizes don't tile cleanly into `columns`): are users bothered, or is "drag to fill" enough?

Don't pick a direction from this section without first looking at a populated cockpit deployment — these are all ergonomic questions that depend on real card distributions, not framework theory.
