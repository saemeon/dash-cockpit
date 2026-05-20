"""The Dash-app shell — sidebar nav, page rendering, and export modal."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, dcc, html, no_update

if TYPE_CHECKING:
    from dash.development.base_component import Component

from dash_cockpit._actions import STD_SETTINGS
from dash_cockpit._chrome import (
    SETTINGS_DRAWER_BODY_ID,
    SETTINGS_DRAWER_ID,
    build_about_modal,
    build_settings_drawer,
    register_about_callback,
    resolve_settings_for,
)
from dash_cockpit._configurator import (
    WORKING_LIST_STORE_ID,
    configurator_export_data,
    register_configurator_callbacks,
)
from dash_cockpit._export import ExportBackend, export_page
from dash_cockpit._layout import render_page
from dash_cockpit._packing import (
    EDIT_MODE_STORE_ID,
    EDIT_MODE_TOGGLE_ID,
    GRID_RESIZE_TICK_ID,
    PAGE_CONTENT_ID,
    register_edit_mode_callbacks,
    register_layout_callbacks,
    register_square_cell_callbacks,
)
from dash_cockpit._page import ConfiguratorPage, Page
from dash_cockpit._presets import PresetStore
from dash_cockpit._refresh import register_refresh_callbacks
from dash_cockpit._registry import CardRegistry

# No app-level CSS — Mantine handles all the visual styling and dcc.Link
# handles routing, so we don't need anything custom.


APPSHELL_ID = "_cockpit_appshell"
NAVBAR_BURGER_ID = "_cockpit_navbar_burger"

# Global settings — a single gear button in the header opens a modal
# whose contents are app-wide preferences (theme, edit mode, where
# per-card settings open). All three preferences persist to localStorage
# so they survive reloads.
GEAR_BUTTON_ID = "_cockpit_settings_gear"
GLOBAL_SETTINGS_MODAL_ID = "_cockpit_global_settings_modal"
THEME_STORE_ID = "_cockpit_theme_pref"  # values: "light" | "dark" | "auto"
SETTINGS_STYLE_STORE_ID = "_cockpit_settings_style_pref"  # "modal" | "sidebar"

# Persistent right-hand aside that hosts per-card settings when the user's
# settings-style pref is "sidebar". When pref is "modal" (the default),
# the aside stays collapsed and the existing dmc.Drawer is used instead.
SETTINGS_ASIDE_ID = "_cockpit_settings_aside"
SETTINGS_ASIDE_BODY_ID = "_cockpit_settings_aside_body"
SETTINGS_ASIDE_TITLE_ID = "_cockpit_settings_aside_title"
SETTINGS_ASIDE_CLOSE_ID = "_cockpit_settings_aside_close"

MANTINE_PROVIDER_ID = "_cockpit_mantine_provider"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Lowercase ``name``, collapse non-alnum runs to ``-``, strip edges."""
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def _page_slug(page: Page) -> str:
    """Stable URL slug for a page — explicit ``id`` if set, else slugified name."""
    if page.id:
        return page.id
    slug = _slugify(page.name)
    if not slug:
        raise ValueError(
            f"Page name {page.name!r} produced an empty slug; set page.id explicitly."
        )
    return slug


_NAV_LINK_TYPE = "_cockpit_nav"


def _nav_link(page: Page, slug: str) -> Component:
    """Build one sidebar nav link pointing at ``/<slug>``.

    ``dmc.NavLink`` (Mantine's sidebar item) provides the visual; ``dcc.Link``
    handles the routing. ``dcc.Link`` does the actual URL update via the
    History API; ``dmc.NavLink`` renders inside it. With
    ``dcc.Location(refresh=False)`` set on the app shell, no full page reload
    happens and the click resolves cleanly.

    ``active`` is server-side, driven by a pattern-matching callback watching
    ``dcc.Location.pathname`` — see :meth:`CockpitApp._register_callbacks`.
    """
    return dcc.Link(
        dmc.NavLink(
            label=page.name,
            id={"type": _NAV_LINK_TYPE, "slug": slug},
            active=False,
        ),
        href=f"/{slug}",
        refresh=False,
        style={"textDecoration": "none", "color": "inherit", "display": "block"},
    )


def _backend_filename(backend: ExportBackend, page_name: str, label: str) -> str:
    """Pick a download filename — backend's ``filename_for`` wins, else fall back.

    Parameters
    ----------
    backend : ExportBackend
        Active backend. If it implements ``filename_for(page_name) -> str``,
        that result is used.
    page_name : str
        Name of the page being exported. Sanitised for filesystem safety in
        the fallback path.
    label : str
        Format label from the modal (e.g. ``"CSV Zip"``). The first word
        becomes the file extension in the fallback path.

    Returns
    -------
    str
        Filename including extension.
    """
    fn = getattr(backend, "filename_for", None)
    if callable(fn):
        return fn(page_name)
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (page_name or "page")
    )
    ext = label.lower().split()[0] or "bin"
    return f"{safe}.{ext}"


class CockpitApp:
    """Cards-first Dash app — sidebar nav, page rendering, optional export.

    Wraps a :class:`dash.Dash` instance with the cockpit's structure: a
    fixed sidebar listing pages, a content area that renders the current
    page, and an optional download modal driven by registered export
    backends.

    Parameters
    ----------
    registry : CardRegistry
        Pre-populated registry of cards and templates.
    pages : list[Page]
        Pages shown in the sidebar in declaration order. Each page is
        addressable at ``/<slug>`` — the slug is ``page.id`` if set, else
        derived from ``page.name`` (lowercased, non-alphanumerics → ``-``).
        Duplicate slugs raise :class:`ValueError` at construction. The first
        page is the default for ``/`` and unrecognised slugs.
    title : str, optional
        Browser tab title and sidebar header. By default ``"Cockpit"``.
    theme : str, optional
        Optional external stylesheet URL for ``dash.Dash``. Pre-M5.5 the
        cockpit was Bootstrap-themed; under Mantine no external stylesheet
        is needed for the cockpit's own components. Pass a Bootstrap-theme
        URL only if your card bodies still rely on Bootstrap utility
        classNames (``text-muted``, ``mb-2``, …). By default ``None``.
    export_backends : dict[str, ExportBackend], optional
        Format label → backend mapping. When non-empty, a "Download report"
        button appears in the sidebar and a format-radio modal lets the user
        pick a backend. By default ``None`` (no export UI).
    preset_store : PresetStore, optional
        Backend for the preset library. When provided, every
        :class:`ConfiguratorPage` shows a Load/Save preset section in its
        sidebar. Curated presets seeded into the store appear alongside
        user-saved ones. By default ``None`` (no preset UI).
    content_max_width : int or None, optional
        Pixel cap on the page-content area's width. Above this width the
        content stays centered with empty margins (no full-screen stretch
        on ultra-wide monitors). Pass ``None`` to disable the cap (legacy
        ``flex: 1`` behaviour). By default ``1600``.

    Attributes
    ----------
    app : dash.Dash
        The underlying Dash app, exposed for advanced wiring (custom
        callbacks, server settings).
    server : flask.Flask
        The underlying Flask server, useful when deploying behind a WSGI
        host.

    Examples
    --------
    >>> from dash_cockpit import CardRegistry, CockpitApp, TeamPage
    >>> registry = CardRegistry()
    >>> registry.load_packages(["team_finance"])
    >>> app = CockpitApp(
    ...     registry=registry,
    ...     pages=[TeamPage(name="Overview", card_ids=["revenue_trend"])],
    ...     title="Executive Cockpit",
    ... )
    >>> app.run(debug=True)  # doctest: +SKIP
    """

    def __init__(
        self,
        registry: CardRegistry,
        pages: list[Page],
        title: str = "Cockpit",
        theme: str | None = None,
        export_backends: dict[str, ExportBackend] | None = None,
        preset_store: PresetStore | None = None,
        content_max_width: int | None = 1600,
    ) -> None:
        self._registry = registry
        self._pages = pages
        self._title = title
        self._export_backends: dict[str, ExportBackend] = dict(export_backends or {})
        self._preset_store = preset_store
        self._content_max_width = content_max_width
        self._pages_by_slug: dict[str, Page] = {}
        self._slugs: list[str] = []
        for page in pages:
            slug = _page_slug(page)
            if slug in self._pages_by_slug:
                other = self._pages_by_slug[slug].name
                raise ValueError(
                    f"Duplicate page slug {slug!r} (from pages {other!r} "
                    f"and {page.name!r}); set page.id explicitly to disambiguate."
                )
            self._pages_by_slug[slug] = page
            self._slugs.append(slug)
        self._app = dash.Dash(
            __name__,
            external_stylesheets=[theme] if theme else [],
            suppress_callback_exceptions=True,
        )
        self._app.title = title
        self._app.layout = self._build_layout()
        self._register_callbacks()
        register_layout_callbacks(self._app)
        register_edit_mode_callbacks(self._app)
        register_square_cell_callbacks(self._app)
        register_refresh_callbacks(
            self._app, self._registry, self._build_render_context
        )
        register_about_callback(self._app, self._registry)
        self._register_settings_router()
        if any(isinstance(p, ConfiguratorPage) for p in self._pages):
            register_configurator_callbacks(
                self._app,
                self._registry,
                preset_store=self._preset_store,
                context_provider=self._build_render_context,
            )

    def _build_navbar_children(self) -> list[Any]:
        """Contents of the AppShell's navbar (sidebar) — nav links + extras.

        The Edit-layout switch lives in the global settings modal (header
        gear), not here — keeps the navbar focused on navigation.
        """
        nav_items = [
            _nav_link(p, s)
            for p, s in zip(self._pages, self._slugs, strict=True)
        ]
        items: list[Any] = list(nav_items)
        if self._export_backends:
            items.append(dmc.Divider(my="sm"))
            items.append(
                dmc.Button(
                    "Download report",
                    id="_cockpit_export_open",
                    variant="light",
                    size="xs",
                    fullWidth=True,
                )
            )
        return [dmc.Stack(items, gap="xs", p="md")]

    def _build_global_settings_modal(self) -> Component:
        """Build the gear-icon-driven global settings modal.

        Three preferences, each persisted to ``localStorage`` via its own
        ``dcc.Store``:

        - **Appearance** — light / dark / auto. Drives
          ``dmc.MantineProvider.forceColorScheme``.
        - **Edit layout** — when on, grids are draggable/resizable. Same
          store the navbar used to write to (:data:`EDIT_MODE_STORE_ID`).
        - **Card settings panel** — modal (a centered ``dmc.Drawer`` /
          ``dmc.Modal``-style overlay) or sidebar (a persistent right-edge
          ``dmc.AppShellAside`` that pushes content to make room). Cards
          stay blind to this — see the Settings ⋮ click callback in
          :mod:`_chrome` for the routing.
        """
        return dmc.Modal(
            children=dmc.Stack(
                [
                    dmc.Stack(
                        [
                            dmc.Text("Appearance", size="sm", fw=500),
                            dmc.SegmentedControl(
                                id=THEME_STORE_ID + "_control",
                                data=[
                                    {"label": "Light", "value": "light"},
                                    {"label": "Dark", "value": "dark"},
                                    {"label": "Auto", "value": "auto"},
                                ],
                                value="light",
                                fullWidth=True,
                            ),
                        ],
                        gap=4,
                    ),
                    dmc.Switch(
                        id=EDIT_MODE_TOGGLE_ID,
                        label="Edit layout",
                        description=(
                            "Allow drag/resize of cards on team and "
                            "configurator pages."
                        ),
                        checked=False,
                    ),
                    dmc.Stack(
                        [
                            dmc.Text(
                                "Card settings panel", size="sm", fw=500
                            ),
                            dmc.SegmentedControl(
                                id=SETTINGS_STYLE_STORE_ID + "_control",
                                data=[
                                    {"label": "Modal drawer", "value": "modal"},
                                    {"label": "Persistent sidebar", "value": "sidebar"},
                                ],
                                value="modal",
                                fullWidth=True,
                            ),
                            dmc.Text(
                                "How a card's Settings ⋮ opens — as a "
                                "right-edge drawer (modal, dimmed backdrop) "
                                "or as a persistent right sidebar that "
                                "pushes the page to make room.",
                                c="dimmed",
                                size="xs",
                            ),
                        ],
                        gap=4,
                    ),
                ],
                gap="lg",
            ),
            id=GLOBAL_SETTINGS_MODAL_ID,
            title="Cockpit settings",
            opened=False,
            centered=True,
            size="md",
        )

    def _build_export_modal(self) -> Component:
        labels = list(self._export_backends)
        radios = dmc.RadioGroup(
            children=dmc.Stack(
                [dmc.Radio(label=lbl, value=lbl) for lbl in labels],
                gap="xs",
            ),
            id="_cockpit_export_format",
            value=labels[0] if labels else None,
            mb="sm",
        )
        return dmc.Modal(
            [
                dmc.Text("Choose a format:", mb="sm"),
                radios,
                dmc.Text(
                    "",
                    id="_cockpit_export_status",
                    c="dimmed",
                    size="sm",
                    mt="xs",
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Cancel",
                            id="_cockpit_export_cancel",
                            variant="default",
                        ),
                        dmc.Button(
                            "Download",
                            id="_cockpit_export_run",
                            variant="filled",
                        ),
                    ],
                    justify="flex-end",
                    mt="md",
                ),
            ],
            id="_cockpit_export_modal",
            title="Export report",
            opened=False,
            centered=True,
        )

    def _build_layout(self) -> Component:
        content_style: dict[str, Any] = {
            "padding": "24px",
        }
        if self._content_max_width is not None:
            # Cap width and center inside AppShellMain — keeps cards a sensible
            # size on ultra-wide displays.
            content_style["maxWidth"] = f"{self._content_max_width}px"
            content_style["marginLeft"] = "auto"
            content_style["marginRight"] = "auto"
            content_style["width"] = "100%"
        content = html.Div(id=PAGE_CONTENT_ID, style=content_style)

        appshell = dmc.AppShell(
            [
                dmc.AppShellHeader(
                    dmc.Group(
                        [
                            # Left: burger + title.
                            dmc.Group(
                                [
                                    dmc.Burger(
                                        id=NAVBAR_BURGER_ID,
                                        opened=True,
                                        size="sm",
                                        **{"aria-label": "Toggle sidebar"},
                                    ),
                                    dmc.Title(self._title, order=4),
                                ],
                                gap="md",
                                align="center",
                            ),
                            # Right: gear opens the global settings modal.
                            dmc.ActionIcon(
                                "⚙",
                                id=GEAR_BUTTON_ID,
                                variant="subtle",
                                color="gray",
                                size="lg",
                                **{"aria-label": "Cockpit settings"},
                            ),
                        ],
                        h="100%",
                        px="md",
                        align="center",
                        justify="space-between",
                    ),
                ),
                dmc.AppShellNavbar(self._build_navbar_children()),
                dmc.AppShellAside(
                    [
                        # Aside header: title on the left, X-close on the right.
                        # Mirrors the chrome of dmc.Drawer so users see a
                        # consistent header regardless of which surface their
                        # pref selected.
                        dmc.Group(
                            [
                                dmc.Text(
                                    "Settings",
                                    id=SETTINGS_ASIDE_TITLE_ID,
                                    fw=600,
                                ),
                                dmc.ActionIcon(
                                    "✕",
                                    id=SETTINGS_ASIDE_CLOSE_ID,
                                    variant="subtle",
                                    color="gray",
                                    size="sm",
                                    **{"aria-label": "Close settings"},
                                ),
                            ],
                            justify="space-between",
                            align="center",
                            p="md",
                            style={
                                "borderBottom": "1px solid var(--mantine-color-default-border)",
                            },
                        ),
                        html.Div(
                            id=SETTINGS_ASIDE_BODY_ID,
                            style={"padding": "16px", "overflowY": "auto"},
                        ),
                    ],
                    id=SETTINGS_ASIDE_ID,
                ),
                dmc.AppShellMain(content),
            ],
            id=APPSHELL_ID,
            header={"height": 56},
            navbar={
                "width": 220,
                "breakpoint": 0,
                "collapsed": {"desktop": False},
            },
            # The aside is collapsed by default; only the Settings ⋮ click
            # callback opens it (and only when the user's settings-style
            # pref is "sidebar"). Width matches the Drawer's "md" size.
            aside={
                "width": 360,
                "breakpoint": 0,
                "collapsed": {"desktop": True},
            },
            padding=0,
        )

        siblings: list[Any] = [
            # refresh=False so pathname updates from dcc.Link don't trigger
            # a full page reload — the page-content callback re-renders just
            # the active page's content. With the default refresh=True, the
            # interaction with the dmc.AppShell layout produces a "navigates
            # briefly then snaps back" symptom.
            dcc.Location(id="_cockpit_url", refresh=False),
            # User preferences — all persisted to localStorage so they
            # survive reloads. The matching SegmentedControl/Switch in the
            # global settings modal writes to each store via clientside.
            dcc.Store(
                id=EDIT_MODE_STORE_ID, storage_type="local", data=False
            ),
            dcc.Store(
                id=THEME_STORE_ID, storage_type="local", data="light"
            ),
            dcc.Store(
                id=SETTINGS_STYLE_STORE_ID, storage_type="local", data="modal"
            ),
            # Resize tick — bumped clientside on window.resize so square-cell
            # callback re-measures grid widths.
            dcc.Store(id=GRID_RESIZE_TICK_ID, data=0),
            appshell,
            self._build_global_settings_modal(),
            # Standard-action surfaces: About modal + Settings drawer always
            # rendered (auto-injected … items in card_chrome target them).
            build_about_modal(),
            build_settings_drawer(),
        ]
        if self._export_backends:
            siblings.append(self._build_export_modal())
            siblings.append(dcc.Download(id="_cockpit_export_download"))
        # MantineProvider must wrap any dmc components for theming context.
        # ``forceColorScheme`` is driven by the theme-pref store via clientside;
        # we keep an id so the callback can target it.
        return dmc.MantineProvider(
            html.Div(siblings),
            id=MANTINE_PROVIDER_ID,
            forceColorScheme="light",
        )

    def _register_settings_router(self) -> None:
        """Route Settings ⋮ clicks to the user's chosen surface (Drawer or Aside).

        The card's settings slot is rendered once via :func:`resolve_settings_for`,
        then sent to *both* containers' bodies. The user's
        ``SETTINGS_STYLE_STORE_ID`` pref decides which container opens —
        the other stays inert (Drawer.opened=False, Aside collapsed). Cards
        stay completely blind to which surface their settings end up in.

        This callback lives here, not in :mod:`_chrome`, so the dependency
        arrow stays right: :mod:`_chrome` (UI builder) is imported by
        :mod:`_app` (orchestrator), never the other way around.
        """
        from dash import ALL, Input, Output, State, callback_context, no_update

        from dash_cockpit._actions import _triggered_card_id

        @self._app.callback(
            Output(SETTINGS_DRAWER_ID, "opened"),
            Output(SETTINGS_DRAWER_ID, "title"),
            Output(SETTINGS_DRAWER_BODY_ID, "children"),
            Output(SETTINGS_ASIDE_TITLE_ID, "children"),
            Output(SETTINGS_ASIDE_BODY_ID, "children"),
            Output(APPSHELL_ID, "aside"),
            Input(
                {
                    "type": "_cockpit_card_action",
                    "card_id": ALL,
                    "action": STD_SETTINGS,
                },
                "n_clicks",
            ),
            State(SETTINGS_STYLE_STORE_ID, "data"),
            prevent_initial_call=True,
        )
        def _on_settings_click(n_clicks_list, style):
            # Initial pattern-match fan-out fires once with all-zeros.
            if not any(n_clicks_list or []):
                return (no_update,) * 6
            card_id = _triggered_card_id(callback_context)
            if card_id is None:
                return (no_update,) * 6

            title, body = resolve_settings_for(
                card_id, self._registry, self._build_render_context()
            )

            sidebar_aside = {
                "width": 360, "breakpoint": 0,
                "collapsed": {"desktop": False},
            }
            modal_aside = {
                "width": 360, "breakpoint": 0,
                "collapsed": {"desktop": True},
            }

            if (style or "modal") == "sidebar":
                # Open the persistent right aside; leave the drawer closed.
                return False, no_update, no_update, title, body, sidebar_aside
            # Default / "modal" — open the Drawer; leave the aside collapsed.
            return True, title, body, no_update, no_update, modal_aside

    def _resolve_page(self, pathname: str | None) -> Page | None:
        """Look up a page by URL slug; fall back to the first page on miss."""
        if not self._pages:
            return None
        slug = (pathname or "").lstrip("/")
        page = self._pages_by_slug.get(slug)
        if page is not None:
            return page
        return self._pages[0]

    def _build_render_context(self) -> dict:
        """Assemble the per-request :class:`RenderContext` for cards.

        Reads Flask's request-scoped state (``flask.g``, ``flask.request``)
        so cards see ``locale`` from the ``Accept-Language`` header and a
        ``request_id`` for log correlation. ``user`` is reserved for auth
        middleware to set on ``flask.g.cockpit_user``; absent today.
        Subclasses (or future ``CockpitConfig``) can override.
        """
        from flask import g, has_request_context, request

        ctx: dict = {}
        if not has_request_context():
            return ctx
        user = getattr(g, "cockpit_user", None)
        if user is not None:
            ctx["user"] = user
        accept = request.accept_languages.best
        if accept:
            ctx["locale"] = accept
        req_id = (
            request.headers.get("X-Request-ID")
            or getattr(g, "cockpit_request_id", None)
        )
        if req_id:
            ctx["request_id"] = req_id
        return ctx

    def _register_callbacks(self) -> None:
        # Gear → open global settings modal.
        self._app.clientside_callback(
            """
            function(n_clicks) {
                if (!n_clicks) return window.dash_clientside.no_update;
                return true;
            }
            """,
            Output(GLOBAL_SETTINGS_MODAL_ID, "opened"),
            Input(GEAR_BUTTON_ID, "n_clicks"),
            prevent_initial_call=True,
        )

        # When the modal opens, hydrate both SegmentedControls from the stores.
        # Triggered by modal.opened (not by the stores), so there is no cycle
        # with the control→store write-backs below.
        self._app.clientside_callback(
            """
            function(opened, theme, style) {
                if (!opened) return [window.dash_clientside.no_update,
                                     window.dash_clientside.no_update];
                return [theme || 'light', style || 'modal'];
            }
            """,
            Output(THEME_STORE_ID + "_control", "value"),
            Output(SETTINGS_STYLE_STORE_ID + "_control", "value"),
            Input(GLOBAL_SETTINGS_MODAL_ID, "opened"),
            State(THEME_STORE_ID, "data"),
            State(SETTINGS_STYLE_STORE_ID, "data"),
            prevent_initial_call=True,
        )

        # Control → store. Triggered by user interaction only (prevent_initial_call).
        self._app.clientside_callback(
            "function(v) { return v || 'light'; }",
            Output(THEME_STORE_ID, "data"),
            Input(THEME_STORE_ID + "_control", "value"),
            prevent_initial_call=True,
        )
        self._app.clientside_callback(
            "function(v) { return v || 'modal'; }",
            Output(SETTINGS_STYLE_STORE_ID, "data"),
            Input(SETTINGS_STYLE_STORE_ID + "_control", "value"),
            prevent_initial_call=True,
        )

        # Theme store → MantineProvider. "auto" maps to None so Mantine
        # uses the OS preference; light/dark force the corresponding scheme.
        self._app.clientside_callback(
            """
            function(theme) {
                if (theme === 'auto') return null;
                return theme || 'light';
            }
            """,
            Output(MANTINE_PROVIDER_ID, "forceColorScheme"),
            Input(THEME_STORE_ID, "data"),
        )

        # Aside close button → re-emit the AppShell.aside dict with
        # collapsed.desktop=True. The Settings ⋮ click callback sets it
        # back to False when the user opens settings on a card.
        self._app.clientside_callback(
            """
            function(n_clicks) {
                if (!n_clicks) return window.dash_clientside.no_update;
                return {
                    width: 360, breakpoint: 0,
                    collapsed: {desktop: true}
                };
            }
            """,
            Output(APPSHELL_ID, "aside", allow_duplicate=True),
            Input(SETTINGS_ASIDE_CLOSE_ID, "n_clicks"),
            prevent_initial_call=True,
        )

        # Burger toggle ↔ navbar collapsed state. Pure clientside —
        # ``dmc.AppShell.navbar`` is a nested dict, so we re-emit the whole
        # thing on each click. ``Burger.opened`` flips on its own click;
        # we read it and translate to the AppShell's expected shape.
        self._app.clientside_callback(
            """
            function(opened) {
                return {
                    width: 220,
                    breakpoint: 0,
                    collapsed: {desktop: !opened}
                };
            }
            """,
            Output(APPSHELL_ID, "navbar"),
            Input(NAVBAR_BURGER_ID, "opened"),
            prevent_initial_call=True,
        )

        # Active-state for the sidebar — toggle ``dmc.NavLink.active`` on
        # the link whose slug matches the current pathname. Falls back to
        # the first slug for ``/`` and unknown paths, matching
        # :meth:`_resolve_page`.
        @self._app.callback(
            Output({"type": _NAV_LINK_TYPE, "slug": ALL}, "active"),
            Input("_cockpit_url", "pathname"),
            State({"type": _NAV_LINK_TYPE, "slug": ALL}, "id"),
        )
        def _set_active_nav(pathname, ids):
            slug = (pathname or "").lstrip("/")
            if slug not in self._pages_by_slug and self._slugs:
                slug = self._slugs[0]
            return [d.get("slug") == slug for d in ids]

        @self._app.callback(
            Output(PAGE_CONTENT_ID, "children"),
            Input("_cockpit_url", "pathname"),
        )
        def render_content(pathname: str | None):
            page = self._resolve_page(pathname)
            if page is None:
                return html.P("No pages configured.")
            return render_page(
                page,
                self._registry,
                context=self._build_render_context(),
                preset_store=self._preset_store,
            )

        if not self._export_backends:
            return

        @self._app.callback(
            Output("_cockpit_export_modal", "opened"),
            Input("_cockpit_export_open", "n_clicks"),
            Input("_cockpit_export_cancel", "n_clicks"),
            Input("_cockpit_export_run", "n_clicks"),
            State("_cockpit_export_modal", "opened"),
            prevent_initial_call=True,
        )
        def toggle_modal(open_clicks, cancel_clicks, run_clicks, is_open):
            ctx = dash.callback_context
            if not ctx.triggered:
                return is_open
            trigger = ctx.triggered[0]["prop_id"].split(".")[0]
            return trigger == "_cockpit_export_open"

        export_states = [
            State("_cockpit_export_format", "value"),
            State("_cockpit_url", "pathname"),
        ]
        if any(isinstance(p, ConfiguratorPage) for p in self._pages):
            export_states.append(State(WORKING_LIST_STORE_ID, "data"))

        @self._app.callback(
            Output("_cockpit_export_download", "data"),
            Output("_cockpit_export_status", "children"),
            Input("_cockpit_export_run", "n_clicks"),
            *export_states,
            prevent_initial_call=True,
        )
        def run_export(n_clicks, fmt_label, pathname, *extra):
            working = extra[0] if extra else None
            if not n_clicks or not fmt_label:
                return no_update, ""
            backend = self._export_backends.get(fmt_label)
            if backend is None:
                return no_update, f"Unknown format: {fmt_label}"
            page = self._resolve_page(pathname)
            if page is None:
                return no_update, "No active page to export."
            try:
                if isinstance(page, ConfiguratorPage):
                    data = configurator_export_data(working or [], self._registry)
                    if not data.cards:
                        return (
                            no_update,
                            "Working list is empty — add cards before exporting.",
                        )
                    payload = backend.export(data)
                else:
                    payload = export_page(page, self._registry, backend)
            except Exception as e:  # noqa: BLE001 - surface backend errors in UI
                return no_update, f"Export failed: {e}"
            filename = _backend_filename(backend, page.name, fmt_label)
            return dcc.send_bytes(lambda buf: buf.write(payload), filename=filename), ""

    def run(self, **kwargs) -> None:
        """Start the Dash dev server.

        Parameters
        ----------
        **kwargs
            Forwarded verbatim to :meth:`dash.Dash.run`. Common options:
            ``debug=True``, ``port=8050``, ``host="0.0.0.0"``.
        """
        self._app.run(**kwargs)

    @property
    def server(self):
        """The underlying Flask server (for production WSGI deployment)."""
        return self._app.server

    @property
    def app(self) -> dash.Dash:
        """The underlying :class:`dash.Dash` instance."""
        return self._app
