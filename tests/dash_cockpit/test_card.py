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
