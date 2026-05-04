import pytest

from dash_cockpit._card import Card, CardMeta, RenderContext


def test_render_context_keys_all_optional():
    # Frozen contract: every field must be optional so cards can be deployed
    # in environments that don't supply auth/locale/etc.
    assert RenderContext.__required_keys__ == frozenset()
    assert set(RenderContext.__optional_keys__) == {
        "user",
        "locale",
        "page_filters",
        "request_id",
    }


def test_card_meta_keys():
    assert set(CardMeta.__required_keys__) == {
        "id",
        "title",
        "team",
        "description",
        "refresh_interval",
        "category",
    }


def test_card_protocol_structural(simple_card):
    assert isinstance(simple_card, Card)


def test_card_render_returns_component(simple_card):
    result = simple_card.render({})
    assert result is not None


# --- unwrap_render_result ----------------------------------------------------


def test_unwrap_bare_component_treated_as_body():
    from dash import html

    from dash_cockpit._card import unwrap_render_result

    div = html.Div("hi")
    body, settings, actions = unwrap_render_result(div)
    assert body is div
    assert settings is None
    assert actions is None


def test_unwrap_full_slot_dict():
    from dash import html

    from dash_cockpit._card import unwrap_render_result

    body_c = html.Div("body")
    settings_c = html.Div("settings")
    body, settings, actions = unwrap_render_result(
        {"body": body_c, "settings": settings_c, "actions": {"refresh": "Refresh"}}
    )
    assert body is body_c
    assert settings is settings_c
    assert actions == {"refresh": "Refresh"}


def test_unwrap_body_only_dict():
    from dash import html

    from dash_cockpit._card import unwrap_render_result

    body_c = html.Div("body")
    body, settings, actions = unwrap_render_result({"body": body_c})
    assert body is body_c
    assert settings is None
    assert actions is None


def test_unwrap_dict_missing_body_raises():
    from dash import html

    from dash_cockpit._card import unwrap_render_result

    with pytest.raises(ValueError, match="without a 'body' key"):
        unwrap_render_result({"settings": html.Div("s")})
