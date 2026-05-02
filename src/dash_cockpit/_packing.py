"""Grid packing — the only module that knows about layout primitives.

Isolating layout here keeps :mod:`_layout` and :mod:`_configurator` engine-agnostic.
Currently:

- :func:`pack_row` uses Bootstrap row/col (used by ``UserPage``'s 2D ``layout``).
- :func:`pack_grid` uses ``dash-snap-grid``'s :class:`~dash_snap_grid.Grid` for
  drag-drop + resize, with localStorage persistence wired by
  :func:`register_layout_callbacks`.

To swap engines (e.g. to ``ResponsiveGrid`` or another grid component):
rewrite the body of :func:`pack_grid` and the JS in
:func:`register_layout_callbacks`. No other module needs to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_snap_grid import Grid

if TYPE_CHECKING:
    from dash.development.base_component import Component


DEFAULT_ROW_HEIGHT = 280
"""Default pixel height of one grid row.

Cards stretch to fill the cell via ``height: 100%`` on the wrapper Div.
A card declaring ``size=(2, 1)`` is therefore one row tall (``DEFAULT_ROW_HEIGHT``
pixels), and ``size=(2, 2)`` is two rows tall.
"""


CARD_NO_DRAG_CLASS = "card-no-drag"
"""CSS class card authors put on interactive elements to opt them out of drag-start.

Buttons, inputs, dropdowns inside cards normally trigger drag when clicked
because the whole tile is draggable. Add ``className="card-no-drag"`` to
any element that should respond to clicks instead.
"""


# CSS selector passed to Grid.draggableCancel — matches the standard
# interactive HTML elements plus the opt-in class above.
DRAGGABLE_CANCEL_SELECTOR = (
    f"input,select,textarea,button,a,.{CARD_NO_DRAG_CLASS}"
)


GRID_ID_TYPE = "_cockpit_grid"
"""``type`` field of every :class:`Grid`'s pattern-matching id."""

LAYOUT_STORE_ID_TYPE = "_cockpit_layout_store"
"""``type`` field of every layout-persistence :class:`dcc.Store`'s pattern-matching id."""

EDIT_MODE_STORE_ID = "_cockpit_edit_mode_store"
"""ID of the single app-level :class:`dcc.Store` holding edit-mode state."""

EDIT_MODE_TOGGLE_ID = "_cockpit_edit_mode_toggle"
"""ID of the sidebar toggle that flips edit mode on/off."""

PAGE_CONTENT_ID = "_cockpit_page_content"
"""ID of the page-content wrapper used as the edit-mode className target."""

EDIT_MODE_CLASS = "cockpit-edit-mode"
"""CSS class applied to the page-content wrapper when edit mode is on."""

CARD_MENU_CLASS = "cockpit-card-menu"
"""CSS class on per-card ⋮ menu wrappers — hidden in CSS when not in edit mode."""


def grid_id(key: str) -> dict[str, str]:
    """Build a pattern-matching id for a :class:`Grid` instance.

    Parameters
    ----------
    key : str
        Per-grid persistence key (e.g. ``"team:Finance Overview"``).

    Returns
    -------
    dict
        Pattern-matching id of the form ``{"type": _cockpit_grid, "key": key}``.
    """
    return {"type": GRID_ID_TYPE, "key": key}


def layout_store_id(key: str) -> dict[str, str]:
    """Build a pattern-matching id for a layout-persistence :class:`dcc.Store`.

    Parameters
    ----------
    key : str
        Same key passed to :func:`grid_id` so that callbacks pair them up.

    Returns
    -------
    dict
        Pattern-matching id of the form
        ``{"type": _cockpit_layout_store, "key": key}``.
    """
    return {"type": LAYOUT_STORE_ID_TYPE, "key": key}


def col_width(n: int) -> int:
    """Bootstrap column width (out of 12) for ``n`` columns per row.

    Parameters
    ----------
    n : int
        Number of equal columns desired.

    Returns
    -------
    int
        Width per column in Bootstrap's 12-grid units (clamped to ≥ 1).
    """
    return max(1, 12 // n)


def pack_row(
    components: list[Component], *, width_basis: int | None = None
) -> Component:
    """Pack components into one Bootstrap row.

    Used by :class:`UserPage`'s 2D layout, where each row is rendered
    independently with equal-width columns.

    Parameters
    ----------
    components : list[Component]
        Components to pack into a single row.
    width_basis : int, optional
        Divisor for the per-column width. If ``None``, the row equal-divides
        among the components present (``len(components)``). If given, every
        column uses ``col_width(width_basis)`` instead — useful when several
        rows must have visually consistent tile sizes even when the last row
        is partial. By default ``None``.

    Returns
    -------
    Component
        A :class:`dbc.Row` containing one :class:`dbc.Col` per component.
    """
    basis = width_basis if width_basis is not None else len(components)
    w = col_width(basis)
    return dbc.Row(
        [dbc.Col(c, width=w) for c in components],
        className="mb-3",
    )


def pack_grid(
    components: list[Component],
    ids: list[str],
    columns: int,
    *,
    persist_key: str = "default",
    row_height: int = DEFAULT_ROW_HEIGHT,
    sizes: list[tuple[int, int]] | None = None,
    draggable: bool = False,
    resizable: bool = False,
    resize_handles: list[str] | None = None,
) -> Component:
    """Pack a flat list of components into a draggable/resizable grid.

    Each component must have a stable id (``ids[i]``) used to match the
    layout entry's ``i`` field. Components are wrapped in a flex Div so they
    fill exactly the grid cell.

    Cards are auto-placed left-to-right, wrapping at ``columns``. Users can
    then drag/resize at runtime; the new layout is saved to ``localStorage``
    by callbacks registered via :func:`register_layout_callbacks`.

    Parameters
    ----------
    components : list[Component]
        Cards (or any components) to render.
    ids : list[str]
        Stable per-component IDs, parallel to ``components``. Used both as
        React keys and as ``i`` in the grid layout.
    columns : int
        Width of the grid in widget units. A card declaring ``size=(2, 1)``
        spans two columns of an ``columns=4`` grid.
    persist_key : str, optional
        Identifier for this grid's layout in ``localStorage``. Use distinct
        keys per page so layouts don't collide. By default ``"default"``.
    row_height : int, optional
        Pixel height of one grid row. By default :data:`DEFAULT_ROW_HEIGHT`.
    sizes : list[tuple[int, int]], optional
        Per-card ``(w, h)`` hints in grid units. Defaults to ``(1, 1)`` for
        every card. Read from each card's ``CARD_META["size"]`` by callers
        in :mod:`_layout` and :mod:`_configurator`. By default ``None``.
    draggable : bool, optional
        Initial draggable state. The cockpit's edit-mode toggle overrides
        this at runtime via :func:`register_edit_mode_callbacks`. By default
        ``False`` (cards locked until the user enters edit mode).
    resizable : bool, optional
        Initial resizable state. Same edit-mode override as ``draggable``.
        By default ``False``.
    resize_handles : list[str], optional
        Which corners/edges show resize handles. Subset of
        ``["s", "e", "w", "n", "se", "ne", "sw", "nw"]``. ``None`` uses
        ``dash-snap-grid``'s default of ``["se"]`` (south-east corner only).
        Pass all eight to allow resizing from any side. By default ``None``.

    Returns
    -------
    Component
        A :class:`html.Div` containing a sibling :class:`dcc.Store` (for
        layout persistence) and the :class:`Grid`.

    Raises
    ------
    ValueError
        If ``len(components) != len(ids)``.
    """
    if len(components) != len(ids):
        raise ValueError(
            f"pack_grid: components ({len(components)}) and ids ({len(ids)}) length mismatch"
        )

    if not components:
        return html.Div()

    if sizes is None:
        sizes = [(1, 1)] * len(components)

    layout: list[dict] = []
    cursor_x = 0
    cursor_y = 0
    for cid, (w, h) in zip(ids, sizes, strict=False):
        if cursor_x + w > columns:
            cursor_x = 0
            cursor_y += 1
        layout.append(
            {
                "i": cid,
                "x": cursor_x,
                "y": cursor_y,
                "w": w,
                "h": h,
                "minW": 1,
                "minH": 1,
                "maxW": columns,
            }
        )
        cursor_x += w

    # Cell wrapper: every card fills exactly its grid cell (height = row_height * h).
    # Cards must use percent-based or flex layout internally — fixed pixel heights
    # will either clip or leave whitespace.
    cell_style = {
        "height": "100%",
        "width": "100%",
        "display": "flex",
        "flexDirection": "column",
        "overflow": "hidden",
        "boxSizing": "border-box",
    }
    children = [
        html.Div(c, id=cid, style=cell_style, className="cockpit-card-cell")
        for c, cid in zip(components, ids, strict=False)
    ]

    grid_kwargs: dict[str, object] = {
        "id": grid_id(persist_key),
        "cols": columns,
        "rowHeight": row_height,
        "layout": layout,
        "children": children,
        "isDraggable": draggable,
        "isResizable": resizable,
        "compactType": "vertical",
        "margin": [10, 10],
        "containerPadding": [10, 10],
        "draggableCancel": DRAGGABLE_CANCEL_SELECTOR,
    }
    if resize_handles is not None:
        grid_kwargs["resizeHandles"] = list(resize_handles)
    grid = Grid(**grid_kwargs)
    return html.Div(
        [
            dcc.Store(
                id=layout_store_id(persist_key),
                storage_type="local",
            ),
            grid,
        ]
    )


def register_layout_callbacks(app) -> None:
    """Register clientside save/restore callbacks for every grid in the app.

    One pair of pattern-matching callbacks (``MATCH`` on the ``key`` field
    of the grid id) handles every grid the app ever renders. Both callbacks
    run in the browser — there is no server roundtrip on drag/resize.

    The save->restore->save loop is broken by a JSON equality guard inside
    the restore callback.

    Parameters
    ----------
    app : dash.Dash
        The Dash app whose grids should persist their layout. Called once
        from :class:`CockpitApp`.

    Notes
    -----
    Storage is per-browser, per-``persist_key``. Cards added or removed
    across deploys are handled gracefully: ``Grid`` ignores layout entries
    whose ``i`` does not match a child, and new children get auto-placed
    according to the initial layout.
    """
    from dash import MATCH, Input, Output, State

    # Save: any grid layout change writes to its sibling store.
    app.clientside_callback(
        """
        function(layout) {
            if (!layout) return window.dash_clientside.no_update;
            return layout;
        }
        """,
        Output(layout_store_id(MATCH), "data"),
        Input(grid_id(MATCH), "layout"),
        prevent_initial_call=True,
    )

    # Restore: when the store hydrates from localStorage, push back into the grid.
    # Equality guard prevents an infinite save->restore->save loop.
    app.clientside_callback(
        """
        function(timestamp, stored, current) {
            if (!stored || !stored.length) return window.dash_clientside.no_update;
            if (JSON.stringify(stored) === JSON.stringify(current)) {
                return window.dash_clientside.no_update;
            }
            return stored;
        }
        """,
        Output(grid_id(MATCH), "layout"),
        Input(layout_store_id(MATCH), "modified_timestamp"),
        State(layout_store_id(MATCH), "data"),
        State(grid_id(MATCH), "layout"),
    )


def register_edit_mode_callbacks(app) -> None:
    """Wire the app-level edit-mode toggle to grid drag/resize and menu visibility.

    When edit mode is **off** (default), every grid is locked
    (``isDraggable=False``, ``isResizable=False``) and per-card ⋮ menus are
    hidden via CSS. When **on**, grids are unlocked and menus appear.

    Two clientside callbacks:

    - **Toggle** writes the boolean to the edit-mode :class:`dcc.Store`
      whenever the toolbar switch is clicked.
    - **Apply** reads the store and writes ``isDraggable``/``isResizable``
      to every grid (pattern-matching ALL) plus a CSS class on the
      page-content wrapper.

    Parameters
    ----------
    app : dash.Dash
        The app to register on. Called once from :class:`CockpitApp`.
    """
    from dash import ALL, Input, Output, State

    # Toggle the boolean store on switch click.
    app.clientside_callback(
        """
        function(checked, current) {
            if (checked === undefined || checked === null) {
                return window.dash_clientside.no_update;
            }
            if (Boolean(checked) === Boolean(current)) {
                return window.dash_clientside.no_update;
            }
            return Boolean(checked);
        }
        """,
        Output(EDIT_MODE_STORE_ID, "data"),
        Input(EDIT_MODE_TOGGLE_ID, "value"),
        State(EDIT_MODE_STORE_ID, "data"),
    )

    # Apply edit-mode state to every grid + the page-content wrapper.
    app.clientside_callback(
        f"""
        function(editMode, gridIds) {{
            const enabled = Boolean(editMode);
            const gridStates = (gridIds || []).map(() => enabled);
            const className = enabled ? '{EDIT_MODE_CLASS}' : '';
            return [gridStates, gridStates, className];
        }}
        """,
        Output({"type": GRID_ID_TYPE, "key": ALL}, "isDraggable"),
        Output({"type": GRID_ID_TYPE, "key": ALL}, "isResizable"),
        Output(PAGE_CONTENT_ID, "className"),
        Input(EDIT_MODE_STORE_ID, "data"),
        State({"type": GRID_ID_TYPE, "key": ALL}, "id"),
    )
