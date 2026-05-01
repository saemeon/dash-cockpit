"""The Dash-app shell — sidebar nav, page rendering, and export modal."""

from __future__ import annotations

from typing import Any

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update

from dash_cockpit._configurator import (
    WORKING_LIST_STORE_ID,
    configurator_export_data,
    register_configurator_callbacks,
)
from dash_cockpit._export import ExportBackend, export_page
from dash_cockpit._layout import render_page
from dash_cockpit._packing import register_layout_callbacks
from dash_cockpit._page import ConfiguratorPage, Page
from dash_cockpit._refresh import register_refresh_callbacks
from dash_cockpit._registry import CardRegistry


def _nav_link(page: Page, index: int) -> dbc.NavLink:
    """Build one sidebar nav link pointing at ``/<index>``."""
    return dbc.NavLink(
        page.name,
        href=f"/{index}",
        active="exact",
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
        addressable at ``/<index>``; the first is the default.
    title : str, optional
        Browser tab title and sidebar header. By default ``"Cockpit"``.
    theme : str, optional
        Bootstrap theme URL passed to ``dash.Dash``. Use any theme from
        :mod:`dash_bootstrap_components.themes`. By default
        :data:`dbc.themes.BOOTSTRAP`.
    export_backends : dict[str, ExportBackend], optional
        Format label → backend mapping. When non-empty, a "Download report"
        button appears in the sidebar and a format-radio modal lets the user
        pick a backend. By default ``None`` (no export UI).

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
        theme: str = dbc.themes.BOOTSTRAP,
        export_backends: dict[str, ExportBackend] | None = None,
    ) -> None:
        self._registry = registry
        self._pages = pages
        self._title = title
        self._export_backends: dict[str, ExportBackend] = dict(export_backends or {})
        self._app = dash.Dash(
            __name__,
            external_stylesheets=[theme],
            suppress_callback_exceptions=True,
        )
        self._app.title = title
        self._app.layout = self._build_layout()
        self._register_callbacks()
        register_layout_callbacks(self._app)
        register_refresh_callbacks(self._app, self._registry)
        if any(isinstance(p, ConfiguratorPage) for p in self._pages):
            register_configurator_callbacks(self._app, self._registry)

    def _build_sidebar(self) -> html.Div:
        nav_items = [_nav_link(p, i) for i, p in enumerate(self._pages)]
        children: list[Any] = [
            html.H4(self._title, className="p-3 mb-2"),
            dbc.Nav(nav_items, vertical=True, pills=True, className="px-2"),
        ]
        if self._export_backends:
            children.append(
                html.Div(
                    dbc.Button(
                        "Download report",
                        id="_cockpit_export_open",
                        color="secondary",
                        outline=True,
                        size="sm",
                        className="w-100",
                    ),
                    className="px-2 mt-3",
                )
            )
        return html.Div(
            children,
            style={
                "width": "220px",
                "minHeight": "100vh",
                "background": "#f8f9fa",
                "borderRight": "1px solid #dee2e6",
                "flexShrink": "0",
            },
        )

    def _build_export_modal(self) -> dbc.Modal:
        labels = list(self._export_backends)
        radios = dbc.RadioItems(
            id="_cockpit_export_format",
            options=[{"label": lbl, "value": lbl} for lbl in labels],
            value=labels[0] if labels else None,
            className="mb-2",
        )
        return dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Export report")),
                dbc.ModalBody(
                    [
                        html.Div("Choose a format:", className="mb-2"),
                        radios,
                        html.Div(
                            id="_cockpit_export_status",
                            className="text-muted small mt-2",
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Cancel",
                            id="_cockpit_export_cancel",
                            color="secondary",
                            outline=True,
                        ),
                        dbc.Button(
                            "Download", id="_cockpit_export_run", color="primary"
                        ),
                    ]
                ),
            ],
            id="_cockpit_export_modal",
            is_open=False,
        )

    def _build_layout(self) -> html.Div:
        sidebar = self._build_sidebar()
        content = html.Div(
            id="_cockpit_page_content",
            style={"flex": "1", "padding": "24px", "overflowY": "auto"},
        )
        children: list[Any] = [
            dcc.Location(id="_cockpit_url"),
            sidebar,
            content,
        ]
        if self._export_backends:
            children.append(self._build_export_modal())
            children.append(dcc.Download(id="_cockpit_export_download"))
        return html.Div(children, style={"display": "flex", "minHeight": "100vh"})

    def _resolve_page(self, pathname: str | None) -> Page | None:
        if not self._pages:
            return None
        try:
            idx = int((pathname or "/0").lstrip("/"))
        except (ValueError, IndexError):
            idx = 0
        idx = max(0, min(idx, len(self._pages) - 1))
        return self._pages[idx]

    def _register_callbacks(self) -> None:
        @self._app.callback(
            Output("_cockpit_page_content", "children"),
            Input("_cockpit_url", "pathname"),
        )
        def render_content(pathname: str | None):
            page = self._resolve_page(pathname)
            if page is None:
                return html.P("No pages configured.")
            return render_page(page, self._registry)

        if not self._export_backends:
            return

        @self._app.callback(
            Output("_cockpit_export_modal", "is_open"),
            Input("_cockpit_export_open", "n_clicks"),
            Input("_cockpit_export_cancel", "n_clicks"),
            Input("_cockpit_export_run", "n_clicks"),
            State("_cockpit_export_modal", "is_open"),
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
