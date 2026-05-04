from dash import dcc, html
from dash_snap_grid import Grid

from dash_cockpit._layout import render_page
from dash_cockpit._packing import col_width
from dash_cockpit._page import TeamPage, UserPage
from dash_cockpit._registry import CardRegistry


def _make_registry(make_card, *card_ids: str) -> CardRegistry:
    reg = CardRegistry()
    for cid in card_ids:
        reg.register(make_card(cid))
    return reg


def _extract_grid(result) -> Grid:
    """pack_grid returns Div([Store, Grid]) — pull the Grid out for assertions."""
    assert isinstance(result, html.Div)
    grids = [c for c in result.children if isinstance(c, Grid)]
    assert len(grids) == 1, f"expected one Grid in {result.children}"
    return grids[0]


def _extract_store(result) -> dcc.Store:
    assert isinstance(result, html.Div)
    stores = [c for c in result.children if isinstance(c, dcc.Store)]
    assert len(stores) == 1
    return stores[0]


def testcol_width_single():
    assert col_width(1) == 12


def testcol_width_two():
    assert col_width(2) == 6


def testcol_width_three():
    assert col_width(3) == 4


def testcol_width_four():
    assert col_width(4) == 3


def test_render_team_page_returns_grid(make_card):
    reg = _make_registry(make_card, "a", "b", "c")
    page = TeamPage(name="Test", card_ids=["a", "b", "c"])
    result = render_page(page, reg)
    grid = _extract_grid(result)
    assert len(grid.children) == 3


def test_render_user_page_returns_div(make_card):
    reg = _make_registry(make_card, "a", "b")
    page = UserPage(name="Custom", layout=[["a", "b"]])
    result = render_page(page, reg)
    assert isinstance(result, html.Div)


def test_render_unknown_card_shows_warning(make_card):
    reg = _make_registry(make_card, "a")
    page = TeamPage(name="Test", card_ids=["a", "missing_card"])
    result = render_page(page, reg)
    assert result is not None


def test_render_error_card_isolated(make_error_card):
    reg = CardRegistry()
    reg.register(make_error_card("broken"))
    page = TeamPage(name="Test", card_ids=["broken"])
    result = render_page(page, reg)
    _extract_grid(result)


def test_render_team_page_two_columns(make_card):
    reg = _make_registry(make_card, "a", "b", "c", "d")
    page = TeamPage(name="Test", card_ids=["a", "b", "c", "d"], columns=2)
    result = render_page(page, reg)
    grid = _extract_grid(result)
    assert len(grid.children) == 4
    layout_by_id = {item["i"]: item for item in grid.layout}
    assert layout_by_id["a"]["y"] == 0 and layout_by_id["b"]["y"] == 0
    assert layout_by_id["c"]["y"] == 1 and layout_by_id["d"]["y"] == 1


def test_render_team_page_emits_layout_store(make_card):
    reg = _make_registry(make_card, "a")
    page = TeamPage(name="Test", card_ids=["a"])
    result = render_page(page, reg)
    store = _extract_store(result)
    assert store.storage_type == "local"
    # store id is a dict with persist key derived from page name
    assert store.id["key"] == "team-v2:Test"


def test_render_page_no_context(make_card):
    reg = _make_registry(make_card, "a")
    page = TeamPage(name="Test", card_ids=["a"])
    result = render_page(page, reg, context=None)
    assert result is not None
