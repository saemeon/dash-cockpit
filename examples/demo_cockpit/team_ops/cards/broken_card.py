"""Intentionally broken card — demonstrates error isolation."""

CARD_META = {
    "id": "broken_card",
    "title": "Broken Card (demo)",
    "team": "ops",
    "description": "Always fails to demonstrate error boundary",
    "refresh_interval": 0,
    "category": "demo",
    "size": (6, 5),
}


def render(context: dict):
    raise ConnectionError("Simulated data source unavailable")


class _Card:
    CARD_META = CARD_META

    def render(self, context: dict):
        return render(context)


broken_card = _Card()
