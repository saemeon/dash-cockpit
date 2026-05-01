import pytest

from dash_cockpit._registry import CardRegistry, RegistryError


def test_register_card(make_card):
    reg = CardRegistry()
    reg.register(make_card("rev"))
    assert "rev" in reg
    assert len(reg) == 1


def test_get_registered_card(make_card):
    reg = CardRegistry()
    reg.register(make_card("rev"))
    entry = reg.get("rev")
    assert entry["meta"]["id"] == "rev"
    assert callable(entry["render"])


def test_get_missing_raises():
    reg = CardRegistry()
    with pytest.raises(KeyError):
        reg.get("nonexistent")


def test_duplicate_id_raises(make_card):
    reg = CardRegistry()
    reg.register(make_card("rev"))
    with pytest.raises(RegistryError, match="Duplicate card id"):
        reg.register(make_card("rev"))


def test_missing_meta_raises():
    class BadCard:
        CARD_META = {"id": "x", "title": "X"}

        def render(self, ctx):
            pass

    reg = CardRegistry()
    with pytest.raises(RegistryError, match="missing metadata fields"):
        reg.register(BadCard())


def test_all_ids(make_card):
    reg = CardRegistry()
    reg.register(make_card("a"))
    reg.register(make_card("b"))
    assert set(reg.all_ids()) == {"a", "b"}


def test_by_team(make_card):
    reg = CardRegistry()
    reg.register(make_card("a", team="finance"))
    reg.register(make_card("b", team="ops"))
    reg.register(make_card("c", team="finance"))
    assert set(reg.by_team("finance")) == {"a", "c"}
    assert reg.by_team("ops") == ["b"]


def test_by_category(make_card):
    reg = CardRegistry()
    reg.register(make_card("x", category="kpi"))
    reg.register(make_card("y", category="trend"))
    reg.register(make_card("z", category="kpi"))
    assert set(reg.by_category("kpi")) == {"x", "z"}


def test_load_package_no_get_cards():
    import sys
    import types

    mod = types.ModuleType("_fake_no_getcards")
    sys.modules["_fake_no_getcards"] = mod
    try:
        reg = CardRegistry()
        with pytest.raises(RegistryError, match="get_cards"):
            reg.load_package("_fake_no_getcards")
    finally:
        del sys.modules["_fake_no_getcards"]


def test_load_package_success(make_card):
    import sys
    import types

    mod = types.ModuleType("_fake_team")
    mod.get_cards = lambda: [make_card("pkg_card")]
    sys.modules["_fake_team"] = mod
    try:
        reg = CardRegistry()
        ids = reg.load_package("_fake_team")
        assert ids == ["pkg_card"]
        assert "pkg_card" in reg
    finally:
        del sys.modules["_fake_team"]
