from dash_cockpit._card import Card, CardMeta


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
