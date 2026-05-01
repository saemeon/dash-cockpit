"""Grid packing helpers — the only place that knows about Bootstrap row/col.

Isolating layout primitives here lets us swap the engine (e.g. dash-snap-grid)
without touching `_layout.py` or `_configurator.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import dash_bootstrap_components as dbc
from dash import html

if TYPE_CHECKING:
    from dash.development.base_component import Component


def col_width(n: int) -> int:
    """Bootstrap column width (out of 12) for `n` columns per row."""
    return max(1, 12 // n)


def pack_row(components: list[Component], *, width_basis: int | None = None) -> Component:
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


def pack_grid(components: list[Component], columns: int) -> Component:
    """Pack a flat list of components into rows of `columns`, with consistent tile widths."""
    rows = [
        pack_row(components[i : i + columns], width_basis=columns)
        for i in range(0, len(components), columns)
    ]
    return html.Div(rows)
