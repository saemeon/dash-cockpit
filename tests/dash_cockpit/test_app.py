import dash

from dash_cockpit._app import CockpitApp
from dash_cockpit._page import TeamPage
from dash_cockpit._registry import CardRegistry


def _make_app(make_card, card_ids=("rev",), page_name="Finance"):
    reg = CardRegistry()
    for cid in card_ids:
        reg.register(make_card(cid))
    pages = [TeamPage(name=page_name, card_ids=list(card_ids))]
    return CockpitApp(registry=reg, pages=pages)


def test_cockpit_app_server_not_none(make_card):
    app = _make_app(make_card)
    assert app.server is not None


def test_cockpit_app_property(make_card):
    app = _make_app(make_card)
    assert isinstance(app.app, dash.Dash)


def test_cockpit_app_title(make_card):
    reg = CardRegistry()
    reg.register(make_card("x"))
    pages = [TeamPage(name="Overview", card_ids=["x"])]
    app = CockpitApp(registry=reg, pages=pages, title="My Cockpit")
    assert app.app.title == "My Cockpit"


def test_cockpit_app_no_pages():
    reg = CardRegistry()
    app = CockpitApp(registry=reg, pages=[])
    assert app.server is not None


def test_cockpit_app_multiple_pages(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    reg.register(make_card("b"))
    pages = [
        TeamPage(name="Finance", card_ids=["a"]),
        TeamPage(name="Ops", card_ids=["b"]),
    ]
    app = CockpitApp(registry=reg, pages=pages)
    assert app.server is not None


class _StubBackend:
    def export(self, page_data) -> bytes:
        return b"OK"


def test_cockpit_app_without_export_has_no_download_button(make_card):
    app = _make_app(make_card)
    assert "_cockpit_export_open" not in str(app.app.layout)


def test_cockpit_app_with_export_has_download_button(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    pages = [TeamPage(name="Finance", card_ids=["a"])]
    app = CockpitApp(
        registry=reg,
        pages=pages,
        export_backends={"Excel": _StubBackend()},
    )
    layout_str = str(app.app.layout)
    assert "_cockpit_export_open" in layout_str
    assert "_cockpit_export_modal" in layout_str
    assert "_cockpit_export_download" in layout_str
