"""Tests for dash_cockpit._packing — grid packing + layout persistence wiring."""

import dash
import pytest
from dash import dcc, html
from dash_snap_grid import Grid

from dash_cockpit._packing import (
    DEFAULT_ROW_HEIGHT,
    GRID_ID_TYPE,
    LAYOUT_STORE_ID_TYPE,
    col_width,
    grid_id,
    layout_store_id,
    pack_grid,
    pack_row,
    register_layout_callbacks,
)


class TestColWidth:
    def test_single_column(self):
        assert col_width(1) == 12

    def test_two_columns(self):
        assert col_width(2) == 6

    def test_clamps_to_one(self):
        assert col_width(99) == 1


class TestPackRow:
    def test_returns_dbc_row(self):
        result = pack_row([html.Div("a"), html.Div("b")])
        # Two equal columns when no width_basis supplied
        assert len(result.children) == 2
        assert result.children[0].width == 6

    def test_width_basis_keeps_consistent_size(self):
        # 1 component, basis=4 → narrow column even though row is alone
        result = pack_row([html.Div("a")], width_basis=4)
        assert result.children[0].width == col_width(4)


class TestPackGrid:
    def test_returns_div_with_store_and_grid(self):
        result = pack_grid(
            [html.Div("a"), html.Div("b")],
            ids=["a", "b"],
            columns=2,
            persist_key="test:demo",
        )
        assert isinstance(result, html.Div)
        kinds = {type(c) for c in result.children}
        assert dcc.Store in kinds
        assert Grid in kinds

    def test_layout_wraps_at_columns(self):
        result = pack_grid(
            [html.Div("a"), html.Div("b"), html.Div("c"), html.Div("d")],
            ids=["a", "b", "c", "d"],
            columns=2,
        )
        grid = next(c for c in result.children if isinstance(c, Grid))
        layout_by_id = {item["i"]: item for item in grid.layout}
        assert layout_by_id["a"]["y"] == 0 and layout_by_id["b"]["y"] == 0
        assert layout_by_id["c"]["y"] == 1 and layout_by_id["d"]["y"] == 1

    def test_sizes_widen_card(self):
        result = pack_grid(
            [html.Div("wide"), html.Div("small")],
            ids=["wide", "small"],
            columns=4,
            sizes=[(2, 1), (1, 1)],
        )
        grid = next(c for c in result.children if isinstance(c, Grid))
        layout_by_id = {item["i"]: item for item in grid.layout}
        assert layout_by_id["wide"]["w"] == 2
        assert layout_by_id["small"]["w"] == 1

    def test_persist_key_propagates_to_ids(self):
        result = pack_grid(
            [html.Div("a")],
            ids=["a"],
            columns=1,
            persist_key="team:Finance",
        )
        store = next(c for c in result.children if isinstance(c, dcc.Store))
        grid = next(c for c in result.children if isinstance(c, Grid))
        assert store.id == {"type": LAYOUT_STORE_ID_TYPE, "key": "team:Finance"}
        assert grid.id == {"type": GRID_ID_TYPE, "key": "team:Finance"}

    def test_default_row_height(self):
        result = pack_grid([html.Div("a")], ids=["a"], columns=1)
        grid = next(c for c in result.children if isinstance(c, Grid))
        assert grid.rowHeight == DEFAULT_ROW_HEIGHT

    def test_empty_returns_bare_div(self):
        result = pack_grid([], ids=[], columns=2)
        assert isinstance(result, html.Div)
        assert not result.children

    def test_id_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            pack_grid([html.Div("a")], ids=["a", "b"], columns=2)


class TestIdHelpers:
    def test_grid_id_shape(self):
        assert grid_id("k") == {"type": GRID_ID_TYPE, "key": "k"}

    def test_layout_store_id_shape(self):
        assert layout_store_id("k") == {"type": LAYOUT_STORE_ID_TYPE, "key": "k"}


class TestRegisterLayoutCallbacks:
    """Smoke tests — verify the call wires without exploding.

    The clientside callbacks themselves run only in a browser, so we can
    only assert they were registered, not that they execute correctly.
    """

    def test_registers_two_callbacks(self):
        app = dash.Dash(__name__)
        before = len(app.callback_map)
        register_layout_callbacks(app)
        after = len(app.callback_map)
        # One save callback + one restore callback
        assert after - before == 2

    def test_idempotent_within_app_is_not_required(self):
        # Dash forbids re-registering the same Output. Calling twice raises;
        # we just check the first call works cleanly.
        app = dash.Dash(__name__)
        register_layout_callbacks(app)  # must not raise
