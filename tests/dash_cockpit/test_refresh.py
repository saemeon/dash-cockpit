"""Tests for dash_cockpit._refresh — per-card auto-refresh wiring."""

import dash
from dash import dcc, html

from dash_cockpit._refresh import (
    CARD_BODY_ID_TYPE,
    CARD_INTERVAL_ID_TYPE,
    card_body_id,
    card_interval_id,
    register_refresh_callbacks,
    wrap_for_refresh,
)
from dash_cockpit._registry import CardRegistry


class TestIdHelpers:
    def test_body_id_shape(self):
        assert card_body_id("foo") == {"type": CARD_BODY_ID_TYPE, "card_id": "foo"}

    def test_interval_id_shape(self):
        assert card_interval_id("foo") == {
            "type": CARD_INTERVAL_ID_TYPE,
            "card_id": "foo",
        }


class TestWrapForRefresh:
    def test_no_refresh_returns_div_only(self):
        result = wrap_for_refresh(html.Span("hi"), "card_a", 0)
        assert isinstance(result, html.Div)
        # No Interval child when refresh is 0
        kinds = {type(c) for c in (result.children if isinstance(result.children, list) else [result.children])}
        assert dcc.Interval not in kinds

    def test_no_refresh_body_id_is_pattern_matched(self):
        result = wrap_for_refresh(html.Span("hi"), "card_a", 0)
        # Body wrapper has the pattern-matching id
        assert result.id == card_body_id("card_a")

    def test_with_refresh_includes_interval(self):
        result = wrap_for_refresh(html.Span("hi"), "card_a", refresh_interval=10)
        assert isinstance(result, html.Div)
        kinds = [type(c) for c in result.children]
        assert dcc.Interval in kinds
        assert html.Div in kinds

    def test_interval_in_milliseconds(self):
        result = wrap_for_refresh(html.Span("hi"), "card_a", refresh_interval=5)
        interval = next(c for c in result.children if isinstance(c, dcc.Interval))
        assert interval.interval == 5_000

    def test_with_refresh_body_id_targetable(self):
        result = wrap_for_refresh(html.Span("hi"), "card_a", refresh_interval=10)
        body = next(c for c in result.children if isinstance(c, html.Div))
        assert body.id == card_body_id("card_a")

    def test_body_wraps_in_dcc_loading(self):
        """Slow renders should show a spinner instead of looking frozen."""
        result = wrap_for_refresh(html.Span("hi"), "card_a", 0)
        # Body Div contains a dcc.Loading containing the original component.
        loading = result.children
        assert isinstance(loading, dcc.Loading)


class TestRegisterRefreshCallbacks:
    def test_adds_one_callback(self):
        app = dash.Dash(__name__)
        registry = CardRegistry()
        before = len(app.callback_map)
        register_refresh_callbacks(app, registry)
        after = len(app.callback_map)
        assert after - before == 1
