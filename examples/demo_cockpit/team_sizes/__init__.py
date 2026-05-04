"""Size sampler — one card per (w, h) so the user can eyeball the raster.

Each card's title is its grid-unit size; the body shows the same.
"""

from dash import html

# Variety of sizes spanning the 12-column raster.
_SIZES: list[tuple[int, int]] = [
    (1, 1), (2, 1), (3, 1), (4, 1), (6, 1),
    (1, 2), (2, 2), (3, 2), (4, 2), (6, 2),
    (3, 3), (4, 3), (6, 3),
    (4, 4), (6, 4),
    (3, 5), (6, 5),
    (12, 2),
    (12, 4),
]


def _make_card(w: int, h: int):
    label = f"{w} x {h}"
    meta = {
        "id": f"size_{w}x{h}",
        "title": label,
        "team": "sizes",
        "description": f"Size sampler tile {label}",
        "refresh_interval": 0,
        "category": "demo",
        "size": (w, h),
    }

    def render(context: dict):
        return html.Div(
            label,
            style={
                "height": "100%",
                "width": "100%",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "fontWeight": "bold",
                "fontSize": "1.4em",
                "color": "#6c757d",
                "background": "#f1f3f5",
                "borderRadius": "4px",
            },
        )

    class _Card:
        CARD_META = meta

        def render(self, context: dict):
            return render(context)

    return _Card()


_CARDS = [_make_card(w, h) for (w, h) in _SIZES]
SIZE_CARD_IDS = [c.CARD_META["id"] for c in _CARDS]


def get_cards():
    return _CARDS
