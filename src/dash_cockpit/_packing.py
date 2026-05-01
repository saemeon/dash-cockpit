"""Grid packing helpers — the only place that knows about layout primitives.

Isolating layout here lets us swap engines without touching `_layout.py` or
`_configurator.py`. Currently:

- `pack_row` uses Bootstrap row/col (used by UserPage's 2D `layout`).
- `pack_grid` uses dash-snap-grid `Grid` (drag-drop + resize, no persistence yet).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import dash_bootstrap_components as dbc
from dash import html
from dash_snap_grid import Grid

if TYPE_CHECKING:
    from dash.development.base_component import Component


# Default pixel height of one grid row. Cards stretch to fill the cell via
# `height: 100%` on the wrapper Div below.
DEFAULT_ROW_HEIGHT = 280


def col_width(n: int) -> int:
    """Bootstrap column width (out of 12) for `n` columns per row."""
    return max(1, 12 // n)


def pack_row(
    components: list[Component], *, width_basis: int | None = None
) -> Component:
    """Pack components into one Bootstrap row.

    width_basis: if given, every column uses `col_width(width_basis)` (consistent
    tile size across partial rows). If None, columns are equal-divided by the
    number of components in this row.
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
    grid_id: str = "_cockpit_grid",
    row_height: int = DEFAULT_ROW_HEIGHT,
    sizes: list[tuple[int, int]] | None = None,
    draggable: bool = True,
    resizable: bool = True,
) -> Component:
    """Pack a flat list of components into a draggable/resizable grid.

    Each component must have a stable id (`ids[i]`) used to match the layout
    entry's `i` field. Components are wrapped in a full-cell Div so they fill
    the grid cell.

    `sizes` (optional) is a parallel list of `(w, h)` hints in grid units;
    defaults to `(1, 1)` for every card. Cards are auto-placed left-to-right,
    wrapping at `columns`.

    No layout persistence yet — drags reset on reload.
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

    children = [
        html.Div(c, id=cid, style={"height": "100%", "width": "100%", "overflow": "auto"})
        for c, cid in zip(components, ids, strict=False)
    ]

    return Grid(
        id=grid_id,
        cols=columns,
        rowHeight=row_height,
        layout=layout,
        children=children,
        isDraggable=draggable,
        isResizable=resizable,
        compactType="vertical",
        margin=[10, 10],
        containerPadding=[10, 10],
        # Don't start a drag from inputs/buttons inside cards
        draggableCancel="input,select,textarea,button,.card-no-drag",
    )
