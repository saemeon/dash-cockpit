"""Tests for dash_cockpit._presets — generic group-based preset library."""

import dash
import pytest
from dash import dcc, html

from dash_cockpit._presets import (
    PRESET_SAVE_MODAL_ID,
    InMemoryPresetStore,
    LocalFilePresetStore,
    Preset,
    PresetStore,
    register_preset_callbacks,
    render_preset_section,
)

# ---------------------------------------------------------------------------
# Preset dataclass
# ---------------------------------------------------------------------------


class TestPresetDataclass:
    def test_minimal_construction(self):
        p = Preset(name="X")
        assert p.name == "X"
        assert p.group == ""
        assert p.entries == []
        assert p.layout is None

    def test_round_trip_dict(self):
        p = Preset(
            name="X",
            group="team:finance",
            entries=[{"template_id": "t", "params": {"y": 1}}],
            layout=[{"i": "a", "x": 0, "y": 0, "w": 1, "h": 1}],
            description="hello",
            metadata={"author": "alice"},
        )
        assert Preset.from_dict(p.to_dict()) == p

    def test_from_dict_handles_missing_group(self):
        # Backwards-compat: dicts without `group` default to "".
        loaded = Preset.from_dict({"name": "X"})
        assert loaded.group == ""


# ---------------------------------------------------------------------------
# InMemoryPresetStore — minimal, no group filtering
# ---------------------------------------------------------------------------


class TestInMemoryPresetStore:
    def test_satisfies_protocol(self):
        store = InMemoryPresetStore()
        assert isinstance(store, PresetStore)

    def test_seed_initial_presets(self):
        seed = [Preset(name="A", group="g1"), Preset(name="B", group="g2")]
        store = InMemoryPresetStore(initial=seed)
        assert {(p.group, p.name) for p in store.list_presets()} == {
            ("g1", "A"),
            ("g2", "B"),
        }

    def test_save_then_load(self):
        store = InMemoryPresetStore()
        store.save(Preset(name="X", group="g", entries=[{"x": 1}]))
        loaded = store.load("g", "X")
        assert loaded.entries == [{"x": 1}]

    def test_save_overwrites(self):
        store = InMemoryPresetStore()
        store.save(Preset(name="X", description="first"))
        store.save(Preset(name="X", description="second"))
        assert store.load("", "X").description == "second"

    def test_same_name_in_different_groups_coexists(self):
        """Composite key — `(group, name)` — lets two groups share names."""
        store = InMemoryPresetStore()
        store.save(Preset(name="Standard", group="finance"))
        store.save(Preset(name="Standard", group="ops"))
        assert len(store.list_presets()) == 2

    def test_load_missing_raises(self):
        store = InMemoryPresetStore()
        with pytest.raises(KeyError):
            store.load("g", "ghost")

    def test_delete(self):
        store = InMemoryPresetStore(initial=[Preset(name="X", group="g")])
        store.delete("g", "X")
        assert store.list_presets() == []


# ---------------------------------------------------------------------------
# LocalFilePresetStore — env-var defaults
# ---------------------------------------------------------------------------


class TestLocalFileEnvDefaults:
    """Default providers read ``COCKPIT_USER`` from the environment."""

    def test_no_env_user_visible_only_global(self, tmp_path, monkeypatch):
        monkeypatch.delenv("COCKPIT_USER", raising=False)
        store = LocalFilePresetStore(tmp_path)
        # Only "global" is visible by default.
        # Save attempt should fail because no group is writable.
        with pytest.raises(PermissionError):
            store.save(Preset(name="X", group="user:anyone"))

    def test_env_user_makes_user_group_writable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COCKPIT_USER", "alice")
        store = LocalFilePresetStore(tmp_path)
        # Should now be able to save under "user:alice".
        store.save(Preset(name="X", group="user:alice", entries=[{"x": 1}]))
        loaded = store.load("user:alice", "X")
        assert loaded.entries == [{"x": 1}]

    def test_env_user_default_save_group(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COCKPIT_USER", "alice")
        store = LocalFilePresetStore(tmp_path)
        assert store.default_save_group() == "user:alice"

    def test_no_env_user_default_save_group_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("COCKPIT_USER", raising=False)
        store = LocalFilePresetStore(tmp_path)
        assert store.default_save_group() == ""

    def test_custom_env_var_name(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_USER_VAR", "bob")
        monkeypatch.delenv("COCKPIT_USER", raising=False)
        store = LocalFilePresetStore(tmp_path, user_env_var="MY_USER_VAR")
        assert store.default_save_group() == "user:bob"


# ---------------------------------------------------------------------------
# LocalFilePresetStore — custom providers (real auth shape)
# ---------------------------------------------------------------------------


class TestLocalFileProviders:
    """Custom callables override env-based defaults — for real auth."""

    def test_custom_visible_groups(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            visible_groups_provider=lambda: ["global", "team:finance", "user:alice"],
            writable_groups_provider=lambda: ["user:alice", "team:finance"],
            seed=[
                Preset(name="A", group="global"),
                Preset(name="B", group="team:finance"),
                Preset(name="C", group="team:other"),  # not visible
            ],
        )
        names = {(p.group, p.name) for p in store.list_presets()}
        assert names == {("global", "A"), ("team:finance", "B")}

    def test_save_to_team_group(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            visible_groups_provider=lambda: ["team:finance"],
            writable_groups_provider=lambda: ["team:finance"],
        )
        store.save(Preset(name="Q1", group="team:finance"))
        # File goes under the team subdir.
        assert (tmp_path / "team_finance" / "Q1.json").exists()

    def test_save_to_unwritable_group_raises(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            writable_groups_provider=lambda: ["user:alice"],
        )
        with pytest.raises(PermissionError, match="not writable"):
            store.save(Preset(name="X", group="team:finance"))

    def test_delete_unwritable_group_raises(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            writable_groups_provider=lambda: ["user:alice"],
        )
        # Create the file directly so the not-found check doesn't fire first.
        (tmp_path / "team_finance").mkdir()
        (tmp_path / "team_finance" / "X.json").write_text("{}")
        with pytest.raises(PermissionError, match="not writable"):
            store.delete("team:finance", "X")

    def test_seeded_presets_immutable(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            seed=[Preset(name="Standard", group="global")],
            writable_groups_provider=lambda: ["global"],
        )
        with pytest.raises(PermissionError, match="seeded"):
            store.save(Preset(name="Standard", group="global"))
        with pytest.raises(PermissionError, match="seeded"):
            store.delete("global", "Standard")

    def test_two_users_isolated(self, tmp_path):
        current = {"user": "alice"}
        store = LocalFilePresetStore(
            tmp_path,
            visible_groups_provider=lambda: [f"user:{current['user']}"],
            writable_groups_provider=lambda: [f"user:{current['user']}"],
        )
        store.save(Preset(name="my_view", group="user:alice"))
        current["user"] = "bob"
        store.save(Preset(name="my_view", group="user:bob"))
        # Bob sees only his own.
        names = {p.name for p in store.list_presets()}
        assert names == {"my_view"}
        assert store.list_presets()[0].group == "user:bob"

    def test_group_path_traversal_sanitised(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            writable_groups_provider=lambda: ["../../../etc"],
        )
        store.save(Preset(name="X", group="../../../etc"))
        # File must stay within tmp_path.
        for path in tmp_path.rglob("*.json"):
            assert tmp_path in path.parents

    def test_seed_visible_only_when_group_visible(self, tmp_path):
        store = LocalFilePresetStore(
            tmp_path,
            seed=[
                Preset(name="A", group="global"),
                Preset(name="B", group="team:hidden"),
            ],
            visible_groups_provider=lambda: ["global"],
        )
        names = {p.name for p in store.list_presets()}
        assert names == {"A"}


# ---------------------------------------------------------------------------
# UI — render + callbacks
# ---------------------------------------------------------------------------


class TestRenderPresetSection:
    def test_returns_div(self):
        result = render_preset_section([Preset(name="A")])
        assert isinstance(result, html.Div)

    def test_picker_options_show_group_prefix(self):
        result = render_preset_section([
            Preset(name="A", group="global"),
            Preset(name="B", group="user:alice"),
        ])
        dropdowns = [c for c in _walk(result) if isinstance(c, dcc.Dropdown)]
        assert len(dropdowns) == 1
        labels = [o["label"] for o in dropdowns[0].options]
        assert labels == ["global / A", "user:alice / B"]

    def test_picker_label_omits_group_when_empty(self):
        result = render_preset_section([Preset(name="A")])
        dropdown = next(c for c in _walk(result) if isinstance(c, dcc.Dropdown))
        assert dropdown.options[0]["label"] == "A"

    def test_picker_disabled_when_empty(self):
        result = render_preset_section([])
        dropdown = next(c for c in _walk(result) if isinstance(c, dcc.Dropdown))
        assert dropdown.disabled is True

    def test_modal_starts_closed(self):
        result = render_preset_section([])
        modal = _find_by_id(result, PRESET_SAVE_MODAL_ID)
        assert modal is not None
        assert modal.is_open is False


class TestRegisterPresetCallbacks:
    def test_registers_three_callbacks(self):
        app = dash.Dash(__name__)
        app.config.suppress_callback_exceptions = True
        store = InMemoryPresetStore()
        before = len(app.callback_map)
        register_preset_callbacks(app, store, "_test_working_list")
        # Load + modal toggle + save = 3.
        assert len(app.callback_map) - before == 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, list):
        children = [children]
    for c in children:
        if hasattr(c, "children") or hasattr(c, "id"):
            yield from _walk(c)


def _find_by_id(component, target_id):
    for c in _walk(component):
        if getattr(c, "id", None) == target_id:
            return c
    return None
