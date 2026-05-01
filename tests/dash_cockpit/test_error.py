from dash import html

from dash_cockpit._error import _error_card, error_boundary


def test_error_boundary_success(simple_card):
    result = error_boundary(simple_card, {})
    assert isinstance(result, html.Div)


def test_error_boundary_isolates_failure(error_card):
    result = error_boundary(error_card, {})
    assert isinstance(result, html.Div)


def test_error_card_contains_id():
    component = _error_card("my_card", "Something went wrong")
    rendered = str(component)
    assert "my_card" in rendered


def test_error_card_contains_message():
    component = _error_card("my_card", "boom")
    rendered = str(component)
    assert "boom" in rendered


def test_error_boundary_passes_context(simple_card):
    ctx = {"date": "2026-04-30"}
    result = error_boundary(simple_card, ctx)
    assert result is not None
