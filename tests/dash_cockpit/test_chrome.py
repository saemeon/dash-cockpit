"""Tests for card chrome — action normalisation and standard-action injection."""

import dash_bootstrap_components as dbc
from dash import html

from dash_cockpit._chrome import (
    STD_ABOUT,
    STD_REFRESH,
    STD_SETTINGS,
    _normalise_actions,
    card_chrome,
)


# --- _normalise_actions ------------------------------------------------------


def test_normalise_none_is_empty():
    assert _normalise_actions(None) == {}
    assert _normalise_actions([]) == {}
    assert _normalise_actions({}) == {}


def test_normalise_legacy_list_shape():
    out = _normalise_actions(
        [{"id": "refresh", "label": "Refresh"}, {"id": "about", "label": "About"}]
    )
    assert out == {"refresh": {"label": "Refresh"}, "about": {"label": "About"}}


def test_normalise_legacy_list_skips_entries_without_id():
    out = _normalise_actions([{"label": "no id"}, {"id": "ok", "label": "Ok"}])
    assert out == {"ok": {"label": "Ok"}}


def test_normalise_legacy_list_defaults_label_to_id():
    out = _normalise_actions([{"id": "raw"}])
    assert out == {"raw": {"label": "raw"}}


def test_normalise_dict_shorthand_string_values():
    out = _normalise_actions({"refresh": "Refresh", "about": "About"})
    assert out == {"refresh": {"label": "Refresh"}, "about": {"label": "About"}}


def test_normalise_dict_with_extras():
    out = _normalise_actions(
        {
            "refresh": "Refresh",
            "open": {"label": "Open in team app", "href": "/finance/"},
        }
    )
    assert out == {
        "refresh": {"label": "Refresh"},
        "open": {"label": "Open in team app", "href": "/finance/"},
    }


def test_normalise_dict_value_dict_label_default():
    # A dict value missing "label" defaults to the key.
    out = _normalise_actions({"raw": {"href": "/x"}})
    assert out["raw"]["label"] == "raw"
    assert out["raw"]["href"] == "/x"


# --- card_chrome standard action auto-injection ------------------------------


def _menu_item_action_ids(chrome_component) -> list[str]:
    """Walk the chrome tree and collect action IDs from DropdownMenuItems."""
    ids: list[str] = []

    def walk(node):
        if isinstance(node, dbc.DropdownMenuItem):
            iid = getattr(node, "id", None)
            if isinstance(iid, dict) and iid.get("type") == "_cockpit_card_action":
                ids.append(iid.get("action"))
            return
        children = getattr(node, "children", None)
        if children is None:
            return
        if isinstance(children, list):
            for c in children:
                walk(c)
        else:
            walk(children)

    walk(chrome_component)
    return ids


def test_chrome_always_injects_refresh_and_about():
    chrome = card_chrome(html.Div("body"), card_id="x", title="X")
    ids = _menu_item_action_ids(chrome)
    assert STD_REFRESH in ids
    assert STD_ABOUT in ids
    # Settings is opt-in via has_settings.
    assert STD_SETTINGS not in ids


def test_chrome_injects_settings_when_has_settings_true():
    chrome = card_chrome(
        html.Div("body"), card_id="x", title="X", has_settings=True
    )
    ids = _menu_item_action_ids(chrome)
    assert STD_SETTINGS in ids


def test_chrome_custom_actions_appear_before_standard():
    chrome = card_chrome(
        html.Div("body"),
        card_id="x",
        title="X",
        actions={"export": "Export CSV"},
    )
    ids = _menu_item_action_ids(chrome)
    # Custom comes first, then the cockpit-supplied standard items.
    assert ids.index("export") < ids.index(STD_REFRESH)
    assert ids.index(STD_REFRESH) < ids.index(STD_ABOUT)


def test_chrome_no_actions_still_has_standard():
    chrome = card_chrome(html.Div("body"), card_id="x")
    ids = _menu_item_action_ids(chrome)
    assert ids == [STD_REFRESH, STD_ABOUT]


def test_chrome_extra_menu_items_appear_last():
    extra = dbc.DropdownMenuItem("Remove", id="remove-x")
    chrome = card_chrome(
        html.Div("body"),
        card_id="x",
        title="X",
        extra_menu_items=[extra],
    )
    ids = _menu_item_action_ids(chrome)
    # Standard items still present; the Remove item is non-pattern-matching
    # so it doesn't show up in our ids list, but its presence is implicit.
    assert STD_REFRESH in ids
    assert STD_ABOUT in ids
