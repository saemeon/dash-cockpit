"""Preset library — saved snapshots of a configurator's working list.

A :class:`Preset` is a JSON-serialisable bundle of configurator state:
the list of template instantiations, optionally the grid layout, plus a
name and a group. The ``group`` is an opaque string namespace — the
framework prescribes no taxonomy; deployments invent their own (e.g.
``"global"``, ``"team:finance"``, ``"user:alice"``).

A :class:`PresetStore` filters which groups are visible/writable to the
current viewer. The default :class:`LocalFilePresetStore` reads the
current user from an environment variable (``COCKPIT_USER`` by default)
and scopes accordingly. Override the providers for real auth integration.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Type aliases for the optional callables `LocalFilePresetStore` accepts.
# All take no args and read request-scoped state internally.
VisibleGroupsProvider = Callable[[], list[str]]
"""Callable returning the groups the current viewer can see in the picker."""

WritableGroupsProvider = Callable[[], list[str]]
"""Callable returning the groups the current viewer can save/delete in."""

DefaultSaveGroupProvider = Callable[[], str]
"""Callable returning the group new user-saves go into by default."""


@dataclass(frozen=True)
class Preset:
    """A named snapshot of a configurator working list, ready to load.

    Parameters
    ----------
    name : str
        Display name. Unique within ``group``.
    group : str, optional
        Opaque namespace. Two presets in different groups can share a name.
        Conventional values: ``"global"``, ``"team:<name>"``, ``"user:<id>"``,
        but the framework accepts any string. Empty string means
        ungrouped (single-bucket mode). By default ``""``.
    entries : list[dict]
        Working-list entries in the configurator's format:
        ``[{"template_id": str, "params": dict}, ...]``.
    layout : list[dict], optional
        Saved grid layout entries (``{i, x, y, w, h}``). ``None`` lets the
        cockpit auto-place cards on load. By default ``None``.
    description : str, optional
        Free-form description shown in the picker. By default ``""``.
    metadata : dict, optional
        Free-form bag for backend-specific extras (timestamps, author,
        version). By default ``{}``.
    """

    name: str
    group: str = ""
    entries: list[dict] = field(default_factory=list)
    layout: list[dict] | None = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Preset:
        """Build from a dict (e.g. round-tripped through JSON)."""
        return cls(
            name=data["name"],
            group=data.get("group", ""),
            entries=list(data.get("entries", [])),
            layout=data.get("layout"),
            description=data.get("description", ""),
            metadata=dict(data.get("metadata", {})),
        )


@runtime_checkable
class PresetStore(Protocol):
    """CRUD interface for preset storage backends.

    Implementations can keep state in memory, on disk, in a database, or
    anywhere else. The cockpit treats them uniformly — pass any conforming
    object to :class:`CockpitApp(preset_store=...)`.

    Implementations are responsible for any group-based access control
    (visibility, write permission). Calls that violate the active viewer's
    permissions should raise :class:`PermissionError`.
    """

    def list_presets(self) -> list[Preset]:
        """Return all presets visible to the current viewer, in display order."""
        ...

    def save(self, preset: Preset) -> None:
        """Insert or update a preset. Overwrites by ``(group, name)``.

        Raises
        ------
        PermissionError
            If ``preset.group`` is not writable by the current viewer.
        """
        ...

    def load(self, group: str, name: str) -> Preset:
        """Look up a preset by ``(group, name)``.

        Raises
        ------
        KeyError
            If no preset with that ``(group, name)`` exists.
        """
        ...

    def delete(self, group: str, name: str) -> None:
        """Remove a preset by ``(group, name)``.

        Raises
        ------
        KeyError
            If no preset with that ``(group, name)`` exists.
        PermissionError
            If ``group`` is not writable by the current viewer.
        """
        ...


class InMemoryPresetStore:
    """Dict-backed preset store. Good for tests and demos.

    Does not enforce visibility or write permissions — every preset is
    visible and writable. Use :class:`LocalFilePresetStore` for a more
    realistic store with group filtering.

    Parameters
    ----------
    initial : list[Preset], optional
        Seed presets. By default ``None`` (empty store).

    Examples
    --------
    >>> store = InMemoryPresetStore(initial=[Preset(name="Default")])
    >>> store.list_presets()
    [Preset(name='Default', ...)]
    """

    def __init__(self, initial: list[Preset] | None = None) -> None:
        self._presets: dict[tuple[str, str], Preset] = {}
        for p in initial or []:
            self._presets[(p.group, p.name)] = p

    def list_presets(self) -> list[Preset]:
        return list(self._presets.values())

    def save(self, preset: Preset) -> None:
        self._presets[(preset.group, preset.name)] = preset

    def load(self, group: str, name: str) -> Preset:
        key = (group, name)
        if key not in self._presets:
            raise KeyError(f"Preset {group!r}/{name!r} not found")
        return self._presets[key]

    def delete(self, group: str, name: str) -> None:
        key = (group, name)
        if key not in self._presets:
            raise KeyError(f"Preset {group!r}/{name!r} not found")
        del self._presets[key]


class LocalFilePresetStore:
    """Filesystem-backed preset store with group-based visibility.

    Storage layout: ``<directory>/<sanitised-group>/<sanitised-name>.json``.
    Presets with ``group=""`` go directly under ``<directory>/``.

    Parameters
    ----------
    directory : str | Path
        Root directory for preset files. Created on first save.
    seed : list[Preset], optional
        In-memory presets layered on top of disk presets. Read-only — never
        written to disk and cannot be deleted via the UI. Use for shipped
        defaults that should always be visible. By default ``None``.
    visible_groups_provider : VisibleGroupsProvider, optional
        Callable returning the groups visible to the current viewer.
        Invoked per operation, so it can read request-scoped state. When
        ``None``, defaults to env-var-based: ``["global", f"user:{u}"]`` if
        ``COCKPIT_USER`` is set, else ``["global"]``. Pass an explicit
        callable for real auth (e.g. ``lambda: ["global", f"user:{g.user_id}"]``).
        By default ``None``.
    writable_groups_provider : WritableGroupsProvider, optional
        Callable returning the groups the current viewer may save to or
        delete from. Defaults to env-var-based: ``[f"user:{u}"]`` if
        ``COCKPIT_USER`` is set, else ``[]`` (no writes). By default ``None``.
    default_save_group_provider : DefaultSaveGroupProvider, optional
        Callable returning the group used when saving a preset that
        doesn't already specify one. Defaults to env-var-based:
        ``f"user:{u}"`` if ``COCKPIT_USER`` is set, else ``""``.
        By default ``None``.
    user_env_var : str, optional
        Name of the environment variable consulted by the default
        providers. By default ``"COCKPIT_USER"``.

    Notes
    -----
    Files are named ``{sanitised-name}.json``. Save is atomic (write to
    temp, rename). Load tolerates missing/corrupt files by skipping them
    in :meth:`list_presets` (with a printed warning).
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        seed: list[Preset] | None = None,
        visible_groups_provider: VisibleGroupsProvider | None = None,
        writable_groups_provider: WritableGroupsProvider | None = None,
        default_save_group_provider: DefaultSaveGroupProvider | None = None,
        user_env_var: str = "COCKPIT_USER",
    ) -> None:
        self._root = Path(directory)
        self._seed = list(seed or [])
        self._user_env_var = user_env_var
        self._visible_groups_provider = (
            visible_groups_provider or self._default_visible_groups
        )
        self._writable_groups_provider = (
            writable_groups_provider or self._default_writable_groups
        )
        self._default_save_group_provider = (
            default_save_group_provider or self._default_save_group
        )

    # ---- env-var-based defaults --------------------------------------

    def _env_user(self) -> str | None:
        return os.environ.get(self._user_env_var) or None

    def _default_visible_groups(self) -> list[str]:
        user = self._env_user()
        return ["global", f"user:{user}"] if user else ["global"]

    def _default_writable_groups(self) -> list[str]:
        user = self._env_user()
        return [f"user:{user}"] if user else []

    def _default_save_group(self) -> str:
        user = self._env_user()
        return f"user:{user}" if user else ""

    # ---- helpers -----------------------------------------------------

    def _group_dir(self, group: str) -> Path:
        if not group:
            return self._root
        return self._root / _sanitise(group)

    def _file_for(self, group: str, name: str) -> Path:
        return self._group_dir(group) / f"{_sanitise(name)}.json"

    def _check_writable(self, group: str) -> None:
        writable = self._writable_groups_provider()
        if group not in writable:
            raise PermissionError(
                f"Group {group!r} is not writable for current viewer "
                f"(writable: {writable})"
            )

    # ---- protocol surface --------------------------------------------

    def default_save_group(self) -> str:
        """Return the group that new user-saves should go into.

        Exposed for the UI: the save modal reads this to know where the
        new preset will land (and shows it to the user).
        """
        return self._default_save_group_provider()

    def list_presets(self) -> list[Preset]:
        visible = set(self._visible_groups_provider())
        # Seeded presets first, in declaration order.
        result: list[Preset] = [p for p in self._seed if p.group in visible]

        # Then disk presets, scanned in stable order: visible groups in
        # provider order, files within each group sorted by name.
        for group in self._visible_groups_provider():
            group_dir = self._group_dir(group)
            if not group_dir.exists():
                continue
            for path in sorted(group_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    # Disk file's group must match its containing dir; coerce
                    # so seed/disk collisions on (group, name) deduplicate later.
                    data["group"] = group
                    result.append(Preset.from_dict(data))
                except (OSError, ValueError, KeyError) as e:  # noqa: PERF203
                    print(f"[preset-store] skipping {path}: {e}")

        return result

    def save(self, preset: Preset) -> None:
        # Reject saving to a seeded group (they're read-only).
        if any(p.group == preset.group and p.name == preset.name for p in self._seed):
            raise PermissionError(
                f"Preset {preset.group!r}/{preset.name!r} is seeded and read-only"
            )
        self._check_writable(preset.group)
        target = self._file_for(preset.group, preset.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(preset.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(target)

    def load(self, group: str, name: str) -> Preset:
        # Seed first — wins over disk for the same (group, name).
        for p in self._seed:
            if p.group == group and p.name == name:
                return p
        target = self._file_for(group, name)
        if not target.exists():
            raise KeyError(f"Preset {group!r}/{name!r} not found")
        data = json.loads(target.read_text(encoding="utf-8"))
        data["group"] = group  # coerce to dir's group
        return Preset.from_dict(data)

    def delete(self, group: str, name: str) -> None:
        # Seeded presets are immutable.
        if any(p.group == group and p.name == name for p in self._seed):
            raise PermissionError(
                f"Preset {group!r}/{name!r} is seeded and read-only"
            )
        self._check_writable(group)
        target = self._file_for(group, name)
        if not target.exists():
            raise KeyError(f"Preset {group!r}/{name!r} not found")
        target.unlink()


def _sanitise(value: str) -> str:
    """Reduce a name (group, preset, or user id) to a filesystem-safe stem."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in value)
    return safe or "_"


# ---------------------------------------------------------------------------
# UI integration — pattern-matching IDs, render helpers, callback wiring.
# ---------------------------------------------------------------------------

PRESET_PICKER_ID = "_cockpit_preset_picker"
"""ID of the dropdown listing all visible presets."""

PRESET_LOAD_BTN_ID = "_cockpit_preset_load"
"""ID of the "Load preset" button."""

PRESET_SAVE_BTN_ID = "_cockpit_preset_save"
"""ID of the "Save current as preset" button (opens modal)."""

PRESET_SAVE_MODAL_ID = "_cockpit_preset_save_modal"
"""ID of the save modal."""

PRESET_SAVE_NAME_ID = "_cockpit_preset_save_name"
"""ID of the name-input inside the save modal."""

PRESET_SAVE_DEST_ID = "_cockpit_preset_save_dest"
"""ID of the read-only "Saving to: <group>" line in the save modal."""

PRESET_SAVE_CONFIRM_ID = "_cockpit_preset_save_confirm"
"""ID of the modal's confirm button."""

PRESET_SAVE_CANCEL_ID = "_cockpit_preset_save_cancel"
"""ID of the modal's cancel button."""

PRESET_STATUS_ID = "_cockpit_preset_status"
"""ID of the small status line shown below the picker."""


def _preset_label(preset: Preset) -> str:
    """Format a preset for the picker dropdown: ``"<group> / <name>"``."""
    if not preset.group:
        return preset.name
    return f"{preset.group} / {preset.name}"


def _preset_value(preset: Preset) -> str:
    """JSON-encode ``(group, name)`` as the dropdown value."""
    return json.dumps({"group": preset.group, "name": preset.name})


def _decode_value(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    try:
        decoded = json.loads(value)
        return decoded["group"], decoded["name"]
    except (ValueError, KeyError, TypeError):
        return None


def _resolve_save_target(store: PresetStore) -> str:
    """Ask the store where new saves should go, falling back to ``""``."""
    fn = getattr(store, "default_save_group", None)
    if callable(fn):
        try:
            return fn() or ""
        except Exception:
            return ""
    return ""


def render_preset_section(presets: list[Preset], save_target: str = "") -> object:
    """Render the preset picker + Load/Save buttons + save modal.

    Parameters
    ----------
    presets : list[Preset]
        Presets to show in the picker (already filtered for visibility).
    save_target : str, optional
        Group new user-saves will go into. Shown read-only in the save
        modal. By default ``""``.

    Returns
    -------
    Component
        A :class:`html.Div` for the configurator sidebar.
    """
    import dash_bootstrap_components as dbc
    from dash import dcc, html

    options = [{"label": _preset_label(p), "value": _preset_value(p)} for p in presets]
    selected = options[0]["value"] if options else None

    picker = dcc.Dropdown(
        id=PRESET_PICKER_ID,
        options=options,
        value=selected,
        clearable=False,
        placeholder="No presets",
        disabled=not options,
        className="mb-2",
    )

    save_disabled = not save_target
    buttons = html.Div(
        [
            dbc.Button(
                "Load",
                id=PRESET_LOAD_BTN_ID,
                color="secondary",
                outline=True,
                size="sm",
                className="me-2",
                disabled=not options,
            ),
            dbc.Button(
                "Save current",
                id=PRESET_SAVE_BTN_ID,
                color="secondary",
                outline=True,
                size="sm",
                disabled=save_disabled,
            ),
        ],
        className="mb-2",
    )

    dest_label = save_target if save_target else "(no writable group)"
    modal = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Save preset")),
            dbc.ModalBody(
                [
                    html.Div(
                        [
                            "Saving to: ",
                            html.Strong(dest_label, id=PRESET_SAVE_DEST_ID),
                        ],
                        className="text-muted small mb-3",
                    ),
                    dbc.Label("Preset name", html_for=PRESET_SAVE_NAME_ID),
                    dbc.Input(
                        id=PRESET_SAVE_NAME_ID,
                        type="text",
                        placeholder="My view",
                    ),
                    html.Div(
                        "Saving with an existing name will overwrite it.",
                        className="text-muted small mt-2",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel",
                        id=PRESET_SAVE_CANCEL_ID,
                        color="secondary",
                        outline=True,
                    ),
                    dbc.Button("Save", id=PRESET_SAVE_CONFIRM_ID, color="primary"),
                ]
            ),
        ],
        id=PRESET_SAVE_MODAL_ID,
        is_open=False,
    )

    return html.Div(
        [
            html.H6("Presets", className="mb-2"),
            picker,
            buttons,
            html.Div(id=PRESET_STATUS_ID, className="text-muted small mb-3"),
            modal,
        ]
    )


def register_preset_callbacks(
    app, store: PresetStore, working_list_store_id: str
) -> None:
    """Wire load/save callbacks against the configurator's working-list store.

    Parameters
    ----------
    app : dash.Dash
        The Dash app to register on.
    store : PresetStore
        Backend used to read/write presets.
    working_list_store_id : str
        ID of the configurator's working-list :class:`dcc.Store`.
    """
    from dash import Input, Output, State, no_update

    @app.callback(
        Output(working_list_store_id, "data", allow_duplicate=True),
        Output(PRESET_STATUS_ID, "children", allow_duplicate=True),
        Input(PRESET_LOAD_BTN_ID, "n_clicks"),
        State(PRESET_PICKER_ID, "value"),
        prevent_initial_call=True,
    )
    def _load_preset(n_clicks, value):
        if not n_clicks:
            return no_update, no_update
        decoded = _decode_value(value)
        if decoded is None:
            return no_update, "No preset selected."
        group, name = decoded
        try:
            preset = store.load(group, name)
        except KeyError:
            return no_update, f"Preset {group!r}/{name!r} not found."
        return list(preset.entries), f"Loaded preset: {_preset_label(preset)}"

    @app.callback(
        Output(PRESET_SAVE_MODAL_ID, "is_open"),
        Output(PRESET_SAVE_NAME_ID, "value"),
        Input(PRESET_SAVE_BTN_ID, "n_clicks"),
        Input(PRESET_SAVE_CANCEL_ID, "n_clicks"),
        Input(PRESET_SAVE_CONFIRM_ID, "n_clicks"),
        State(PRESET_SAVE_MODAL_ID, "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_save_modal(open_clicks, cancel_clicks, confirm_clicks, is_open):
        from dash import callback_context

        ctx = callback_context
        if not ctx.triggered:
            return is_open, no_update
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == PRESET_SAVE_BTN_ID:
            return True, ""
        return False, no_update

    @app.callback(
        Output(PRESET_PICKER_ID, "options"),
        Output(PRESET_PICKER_ID, "value"),
        Output(PRESET_STATUS_ID, "children", allow_duplicate=True),
        Input(PRESET_SAVE_CONFIRM_ID, "n_clicks"),
        State(PRESET_SAVE_NAME_ID, "value"),
        State(working_list_store_id, "data"),
        prevent_initial_call=True,
    )
    def _save_preset(n_clicks, name, working):
        if not n_clicks:
            return no_update, no_update, no_update
        if not name or not name.strip():
            return no_update, no_update, "Please enter a preset name."
        name = name.strip()
        target_group = _resolve_save_target(store)
        preset = Preset(
            name=name,
            group=target_group,
            entries=list(working or []),
        )
        try:
            store.save(preset)
        except (OSError, ValueError, PermissionError) as e:
            return no_update, no_update, f"Save failed: {e}"
        new_options = [
            {"label": _preset_label(p), "value": _preset_value(p)}
            for p in store.list_presets()
        ]
        return (
            new_options,
            _preset_value(preset),
            f"Saved preset: {_preset_label(preset)}",
        )
