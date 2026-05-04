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


# --- pin-down #7: package import isolation ----------------------------------


def _install_fake(name, **attrs):
    import sys
    import types

    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _uninstall_fake(*names):
    import sys

    for name in names:
        sys.modules.pop(name, None)


def test_load_packages_isolates_failures(make_card, recwarn):
    # Bad package raises ImportError; good package loads. The failure is
    # recorded (not re-raised) and the good package still ends up in the
    # registry — pin-down #7's whole point.
    _install_fake("_pkg_good", get_cards=lambda: [make_card("ok_card")])
    try:
        reg = CardRegistry()
        reg.load_packages(["_does_not_exist", "_pkg_good"])
        assert "ok_card" in reg
        failures = reg.failures()
        assert "_does_not_exist" in failures
        assert "ok_card" not in failures  # cards aren't in failure map
        # Warned about the bad package
        assert any(
            "_does_not_exist" in str(w.message) for w in recwarn.list
        )
    finally:
        _uninstall_fake("_pkg_good")


def test_load_packages_records_card_registration_failure(make_card):
    # A package whose get_cards() raises is treated as failed.
    def boom():
        raise RuntimeError("data fetch crashed at import")

    _install_fake("_pkg_boom", get_cards=boom)
    _install_fake("_pkg_after", get_cards=lambda: [make_card("after")])
    try:
        reg = CardRegistry()
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reg.load_packages(["_pkg_boom", "_pkg_after"])
        assert reg.failures()["_pkg_boom"].startswith("RuntimeError:")
        # Subsequent package still loaded.
        assert "after" in reg
    finally:
        _uninstall_fake("_pkg_boom", "_pkg_after")


def test_load_packages_strict_reraises(make_card):
    # strict=True restores the pre-#7 fail-fast behaviour.
    reg = CardRegistry()
    with pytest.raises(RegistryError):
        reg.load_packages(["_does_not_exist"], strict=True)
    # Even in strict mode, no failure is recorded for a raised exception
    # (the caller owns the failure once it leaves load_packages).
    assert reg.failures() == {}


def test_failures_default_empty():
    reg = CardRegistry()
    assert reg.failures() == {}


def test_failures_returns_snapshot():
    # Mutating the returned dict must not affect the registry's internal state.
    reg = CardRegistry()
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reg.load_packages(["_does_not_exist"])
    snapshot = reg.failures()
    snapshot.clear()
    assert reg.failures() != {}
