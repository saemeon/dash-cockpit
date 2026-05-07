import dash
import pytest

from dash_cockpit._app import CockpitApp, _page_slug, _slugify
from dash_cockpit._page import ConfiguratorPage, TeamPage, UserPage
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


def test_build_render_context_outside_request_is_empty(make_card):
    # No active Flask request → no headers / no flask.g / no auth user.
    # Cards must still receive a dict (not None), and reading via .get()
    # must not raise — every field is documented as NotRequired.
    app = _make_app(make_card)
    ctx = app._build_render_context()
    assert ctx == {}


def test_build_render_context_inside_request(make_card):
    # When wrapped in a Flask request context, locale comes from
    # Accept-Language, request_id comes from X-Request-ID, user comes
    # from flask.g.cockpit_user (set by future auth middleware).
    app = _make_app(make_card)
    flask_app = app.server
    with flask_app.test_request_context(
        "/finance",
        headers={
            "Accept-Language": "de-CH,de;q=0.9",
            "X-Request-ID": "abc-123",
        },
    ):
        from flask import g

        g.cockpit_user = {"id": "u1", "email": "u@example.com"}
        ctx = app._build_render_context()
    assert ctx["locale"] == "de-CH"
    assert ctx["request_id"] == "abc-123"
    assert ctx["user"] == {"id": "u1", "email": "u@example.com"}


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


# --- Slug-based routing -------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Finance Overview", "finance-overview"),
        ("KPI Builder", "kpi-builder"),
        ("My View!", "my-view"),
        ("  Spaced  ", "spaced"),
        ("Foo / Bar", "foo-bar"),
        ("ALLCAPS", "allcaps"),
        ("a__b__c", "a-b-c"),
    ],
)
def test_slugify_examples(name, expected):
    assert _slugify(name) == expected


def test_page_slug_uses_explicit_id():
    page = TeamPage(name="Finance Overview", card_ids=["x"], id="custom")
    assert _page_slug(page) == "custom"


def test_page_slug_falls_back_to_name():
    page = TeamPage(name="Finance Overview", card_ids=["x"])
    assert _page_slug(page) == "finance-overview"


def test_page_slug_empty_name_raises():
    page = TeamPage(name="!!!", card_ids=["x"])
    with pytest.raises(ValueError, match="empty slug"):
        _page_slug(page)


def _multi_page_app(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    reg.register(make_card("b"))
    reg.register(make_card("c"))
    pages = [
        TeamPage(name="Finance Overview", card_ids=["a"]),
        TeamPage(name="Operations", card_ids=["b"]),
        TeamPage(name="Custom", card_ids=["c"], id="my-slug"),
    ]
    return CockpitApp(registry=reg, pages=pages), pages


def test_resolve_page_by_slug(make_card):
    app, pages = _multi_page_app(make_card)
    assert app._resolve_page("/finance-overview") is pages[0]
    assert app._resolve_page("/operations") is pages[1]
    assert app._resolve_page("/my-slug") is pages[2]


def test_resolve_page_explicit_id_wins_over_name(make_card):
    app, pages = _multi_page_app(make_card)
    # The third page has id="my-slug"; its slugified name "custom" must NOT resolve.
    assert app._resolve_page("/custom") is pages[0]  # falls back to first


def test_resolve_page_root_returns_first(make_card):
    app, pages = _multi_page_app(make_card)
    assert app._resolve_page("/") is pages[0]
    assert app._resolve_page("") is pages[0]
    assert app._resolve_page(None) is pages[0]


def test_resolve_page_unknown_slug_returns_first(make_card):
    app, pages = _multi_page_app(make_card)
    assert app._resolve_page("/nonexistent") is pages[0]


def test_resolve_page_no_pages_returns_none():
    app = CockpitApp(registry=CardRegistry(), pages=[])
    assert app._resolve_page("/anything") is None


def test_duplicate_slug_raises(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    reg.register(make_card("b"))
    pages = [
        TeamPage(name="Foo Bar", card_ids=["a"]),
        TeamPage(name="foo bar", card_ids=["b"]),  # slugifies identically
    ]
    with pytest.raises(ValueError, match="Duplicate page slug 'foo-bar'"):
        CockpitApp(registry=reg, pages=pages)


def test_nav_links_use_slugs(make_card):
    app, _ = _multi_page_app(make_card)
    layout_str = str(app.app.layout)
    assert "/finance-overview" in layout_str
    assert "/operations" in layout_str
    assert "/my-slug" in layout_str
    # Old int-index links must be gone.
    assert "href='/0'" not in layout_str
    assert "href='/1'" not in layout_str


def test_mixed_page_types_get_slugs(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    reg.register(make_card("b"))
    pages = [
        TeamPage(name="Team", card_ids=["a"]),
        UserPage(name="Mine", layout=[["b"]]),
        ConfiguratorPage(name="Builder", template_ids=[]),
    ]
    app = CockpitApp(registry=reg, pages=pages)
    assert app._resolve_page("/team") is pages[0]
    assert app._resolve_page("/mine") is pages[1]
    assert app._resolve_page("/builder") is pages[2]


# ---------------------------------------------------------------------------
# M5.5 global settings — gear, stores, theme, settings-style routing
# ---------------------------------------------------------------------------


def _layout_str(app: CockpitApp) -> str:
    """Render the app's layout to a string for substring assertions."""
    return str(app.app.layout)


def test_layout_has_gear_button(make_card):
    from dash_cockpit._app import GEAR_BUTTON_ID

    app = _make_app(make_card)
    assert GEAR_BUTTON_ID in _layout_str(app)


def test_layout_has_global_settings_modal(make_card):
    from dash_cockpit._app import GLOBAL_SETTINGS_MODAL_ID

    app = _make_app(make_card)
    s = _layout_str(app)
    assert GLOBAL_SETTINGS_MODAL_ID in s
    # Three sections — Appearance, Edit layout, Card settings panel.
    assert "Appearance" in s
    assert "Edit layout" in s
    assert "Card settings panel" in s


def test_layout_has_user_pref_stores(make_card):
    from dash_cockpit._app import (
        EDIT_MODE_STORE_ID,
        SETTINGS_STYLE_STORE_ID,
        THEME_STORE_ID,
    )

    app = _make_app(make_card)
    s = _layout_str(app)
    for store_id in (THEME_STORE_ID, SETTINGS_STYLE_STORE_ID, EDIT_MODE_STORE_ID):
        assert store_id in s


def test_user_pref_stores_persist_to_local_storage(make_card):
    """All three preferences must use storage_type='local' so they survive reloads."""
    from dash import dcc

    from dash_cockpit._app import (
        EDIT_MODE_STORE_ID,
        SETTINGS_STYLE_STORE_ID,
        THEME_STORE_ID,
    )

    app = _make_app(make_card)
    found: dict[str, dcc.Store] = {}

    def walk(node):
        nid = getattr(node, "id", None)
        if isinstance(nid, str) and nid in {
            THEME_STORE_ID, SETTINGS_STYLE_STORE_ID, EDIT_MODE_STORE_ID
        }:
            if isinstance(node, dcc.Store):
                found[nid] = node
        children = getattr(node, "children", None)
        if children is None:
            return
        if isinstance(children, list):
            for c in children:
                walk(c)
        else:
            walk(children)

    walk(app.app.layout)
    assert set(found) == {THEME_STORE_ID, SETTINGS_STYLE_STORE_ID, EDIT_MODE_STORE_ID}
    for store_id, store in found.items():
        assert store.storage_type == "local", (
            f"{store_id} should be storage_type='local' so the pref survives reloads"
        )


def test_layout_has_app_shell_aside(make_card):
    """The aside slot must always be present so the settings router can target it."""
    from dash_cockpit._app import (
        SETTINGS_ASIDE_BODY_ID,
        SETTINGS_ASIDE_ID,
        SETTINGS_ASIDE_TITLE_ID,
    )

    app = _make_app(make_card)
    s = _layout_str(app)
    assert SETTINGS_ASIDE_ID in s
    assert SETTINGS_ASIDE_BODY_ID in s
    assert SETTINGS_ASIDE_TITLE_ID in s


def test_edit_mode_switch_no_longer_in_navbar(make_card):
    """The Edit-layout switch lives in the global settings modal, not the navbar."""
    from dash_cockpit._app import EDIT_MODE_TOGGLE_ID

    app = _make_app(make_card)
    s = _layout_str(app)
    # Switch is still present (just moved out of the navbar — into the modal).
    assert EDIT_MODE_TOGGLE_ID in s
    # Sanity: the switch's label string is still rendered exactly once.
    assert s.count("Edit layout") == 1


def test_resolve_settings_for_known_card(make_card):
    """Drawer-agnostic helper: rendering succeeds → (title, body) returned."""
    from dash_cockpit._chrome import resolve_settings_for

    reg = CardRegistry()
    reg.register(make_card("rev"))
    title, body = resolve_settings_for("rev", reg, {})
    assert "rev" in title or "Settings" in title
    assert body is not None


def test_resolve_settings_for_unknown_card(make_card):
    """Unknown card_id → soft error message, not exception."""
    from dash_cockpit._chrome import resolve_settings_for

    reg = CardRegistry()
    title, body = resolve_settings_for("ghost", reg, {})
    assert title == "Settings"
    body_str = str(body)
    assert "ghost" in body_str
    assert "No card" in body_str


def test_resolve_settings_for_card_without_settings_slot(make_card):
    """Card returns a bare Component (no settings slot) → 'no settings' message."""
    from dash_cockpit._chrome import resolve_settings_for

    reg = CardRegistry()
    reg.register(make_card("rev"))  # make_card returns a card with no settings slot
    _title, body = resolve_settings_for("rev", reg, {})
    # The make_card fixture renders a bare Component, so unwrap → settings is None
    body_str = str(body)
    assert "no settings" in body_str.lower()


def test_resolve_settings_for_card_render_raises(error_card):
    """Card whose render raises → soft error message, drawer/aside still works."""
    from dash_cockpit._chrome import resolve_settings_for

    reg = CardRegistry()
    reg.register(error_card)
    title, body = resolve_settings_for(error_card.CARD_META["id"], reg, {})
    assert "error" in title.lower()
    body_str = str(body)
    assert "Error" in body_str or "error" in body_str


def test_settings_router_callback_is_registered(make_card):
    """One settings-router callback must exist so Settings ⋮ clicks resolve."""
    from dash_cockpit._app import (
        APPSHELL_ID,
        SETTINGS_DRAWER_ID,
        SETTINGS_ASIDE_BODY_ID,
    )

    app = _make_app(make_card)
    # Find the callback whose Outputs include the drawer + aside body + appshell.aside.
    matched = False
    for cb in app.app.callback_map.values():
        outputs = cb.get("output")
        # output may be a single ComponentRegistration or a list
        outs = outputs if isinstance(outputs, list) else [outputs]
        # Keep as list — pattern-matching outputs have dict component_ids
        # which are unhashable.
        out_ids = [getattr(o, "component_id", None) for o in outs]
        if (
            SETTINGS_DRAWER_ID in out_ids
            and SETTINGS_ASIDE_BODY_ID in out_ids
            and APPSHELL_ID in out_ids
        ):
            matched = True
            break
    assert matched, (
        "Expected a settings-router callback writing to both Drawer and Aside "
        "+ AppShell.aside, none found"
    )
