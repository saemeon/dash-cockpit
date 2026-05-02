"""dash-cockpit — cards-first executive analytics cockpit framework for Dash.

Build a single Dash app that aggregates self-contained cards published by
multiple team packages. The cockpit owns layout and navigation; teams own
data and rendering. See ``CLAUDE.md`` for the full design.

Examples
--------
>>> from dash_cockpit import CardRegistry, CockpitApp, TeamPage
>>> registry = CardRegistry()
>>> registry.load_packages(["team_finance", "team_ops"])
>>> app = CockpitApp(
...     registry=registry,
...     pages=[TeamPage(name="Overview", card_ids=["revenue_trend"])],
... )
>>> app.run(debug=True)  # doctest: +SKIP
"""

import os as _os

# dash-snap-grid requires React 18.2; set before any dash import resolves.
_os.environ.setdefault("REACT_VERSION", "18.2.0")

from dash_cockpit._app import CockpitApp
from dash_cockpit._card import Card, CardMeta
from dash_cockpit._export import (
    CardExportEntry,
    ChartCard,
    DocumentCard,
    ExportBackend,
    PageExportData,
    TabularCard,
    build_page_export_data,
    classify_card,
    export_page,
)
from dash_cockpit._packing import CARD_NO_DRAG_CLASS
from dash_cockpit._page import ConfiguratorPage, Page, TeamPage, UserPage
from dash_cockpit._presets import (
    DefaultSaveGroupProvider,
    InMemoryPresetStore,
    LocalFilePresetStore,
    Preset,
    PresetStore,
    VisibleGroupsProvider,
    WritableGroupsProvider,
)
from dash_cockpit._registry import CardRegistry, RegistryError
from dash_cockpit._template import (
    CardTemplate,
    ParameterSpec,
    TemplateMeta,
    card_id_for,
    fanout_params,
)
from dash_cockpit._version import __version__

__all__ = [
    # Cards
    "CARD_NO_DRAG_CLASS",
    "Card",
    "CardMeta",
    # Templates
    "CardTemplate",
    "ParameterSpec",
    "TemplateMeta",
    "card_id_for",
    "fanout_params",
    # Pages
    "ConfiguratorPage",
    "Page",
    "TeamPage",
    "UserPage",
    # Registry
    "CardRegistry",
    "RegistryError",
    # Presets
    "DefaultSaveGroupProvider",
    "InMemoryPresetStore",
    "LocalFilePresetStore",
    "Preset",
    "PresetStore",
    "VisibleGroupsProvider",
    "WritableGroupsProvider",
    # App
    "CockpitApp",
    # Export
    "CardExportEntry",
    "ChartCard",
    "DocumentCard",
    "ExportBackend",
    "PageExportData",
    "TabularCard",
    "build_page_export_data",
    "classify_card",
    "export_page",
    # Misc
    "__version__",
]
