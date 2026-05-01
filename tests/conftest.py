import pytest
from dash import html

from dash_cockpit._card import CardMeta


def _make_meta(**overrides) -> CardMeta:
    base: CardMeta = {
        "id": "test_card",
        "title": "Test Card",
        "team": "test_team",
        "description": "A test card",
        "refresh_interval": 0,
        "category": "test",
    }
    base.update(overrides)
    return base


class _SimpleCard:
    def __init__(self, card_id: str = "test_card", team: str = "test_team", category: str = "test"):
        self.CARD_META = _make_meta(id=card_id, team=team, category=category)

    def render(self, context: dict):
        return html.Div(f"Card: {self.CARD_META['id']}")


class _ErrorCard:
    def __init__(self, card_id: str = "broken_card"):
        self.CARD_META = _make_meta(id=card_id)

    def render(self, context: dict):
        raise RuntimeError("Simulated card failure")


@pytest.fixture
def make_meta():
    return _make_meta


@pytest.fixture
def make_card():
    """Factory fixture: make_card(id, team='...', category='...') -> SimpleCard."""
    return _SimpleCard


@pytest.fixture
def make_error_card():
    return _ErrorCard


@pytest.fixture
def simple_card():
    return _SimpleCard()


@pytest.fixture
def error_card():
    return _ErrorCard()
