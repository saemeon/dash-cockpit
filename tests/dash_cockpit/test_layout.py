from dash import html

from dash_cockpit._layout import render_page
from dash_cockpit._packing import col_width
from dash_cockpit._page import TeamPage, UserPage
from dash_cockpit._registry import CardRegistry


def _make_registry(make_card, *card_ids: str) -> CardRegistry:
    reg = CardRegistry()
    for cid in card_ids:
        reg.register(make_card(cid))
    return reg


def testcol_width_single():
    assert col_width(1) == 12


def testcol_width_two():
    assert col_width(2) == 6


def testcol_width_three():
    assert col_width(3) == 4


def testcol_width_four():
    assert col_width(4) == 3


def test_render_team_page_returns_div(make_card):
    reg = _make_registry(make_card, "a", "b", "c")
    page = TeamPage(name="Test", card_ids=["a", "b", "c"])
    result = render_page(page, reg)
    assert isinstance(result, html.Div)


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
    assert isinstance(result, html.Div)


def test_render_team_page_two_columns(make_card):
    reg = _make_registry(make_card, "a", "b", "c", "d")
    page = TeamPage(name="Test", card_ids=["a", "b", "c", "d"], columns=2)
    result = render_page(page, reg)
    assert isinstance(result, html.Div)
    assert len(result.children) == 2  # 2 rows of 2


def test_render_page_no_context(make_card):
    reg = _make_registry(make_card, "a")
    page = TeamPage(name="Test", card_ids=["a"])
    result = render_page(page, reg, context=None)
    assert result is not None
