from __future__ import annotations

from typing import TYPE_CHECKING, Any

import dash_bootstrap_components as dbc
from dash import dcc, html

from dash_cockpit._error import error_boundary
from dash_cockpit._packing import pack_grid
from dash_cockpit._template import (
    ParameterSpec,
    card_id_for,
    fanout_params,
)

if TYPE_CHECKING:
    import dash
    from dash.development.base_component import Component

    from dash_cockpit._page import ConfiguratorPage
    from dash_cockpit._registry import CardRegistry
    from dash_cockpit._template import CardTemplate


# Public IDs (single configurator per page, so fixed IDs are fine)
TEMPLATE_PICKER_ID = "_cockpit_cfg_template"
FORM_ID = "_cockpit_cfg_form"
ADD_BTN_ID = "_cockpit_cfg_add"
CLEAR_BTN_ID = "_cockpit_cfg_clear"
WORKING_LIST_STORE_ID = "_cockpit_cfg_store"
CARDS_PANE_ID = "_cockpit_cfg_cards"
STATUS_ID = "_cockpit_cfg_status"


def param_input_id(name: str) -> dict[str, str]:
    return {"type": "_cockpit_cfg_param", "name": name}


def remove_btn_id(card_id: str) -> dict[str, str]:
    return {"type": "_cockpit_cfg_remove", "card_id": card_id}


def _field_component(
    spec: ParameterSpec, current_params: dict[str, Any] | None = None
) -> "Component":
    """Render one ParameterSpec as a labelled input.

    If `spec.options_fn` is set, call it with `current_params` to compute
    cascading dropdown options. The `current_params` values are used to
    prefill the input so rerendering the form preserves user choices.
    """
    options = spec.options or []
    if spec.options_fn is not None:
        try:
            options = spec.options_fn(current_params or {}) or []
        except Exception:
            options = spec.options or []
    label = html.Label(
        spec.label, htmlFor=str(param_input_id(spec.name)), className="form-label"
    )

    # current value wins over the static default when present
    if current_params and spec.name in current_params:
        value = current_params.get(spec.name)
    else:
        value = spec.default

    if spec.type == "select":
        widget = dcc.Dropdown(
            id=param_input_id(spec.name),
            options=[{"label": str(o), "value": o} for o in options],
            value=value,
            clearable=not spec.required,
        )
    elif spec.type == "multi_select":
        widget = dcc.Dropdown(
            id=param_input_id(spec.name),
            options=[{"label": str(o), "value": o} for o in options],
            value=value or [],
            multi=True,
        )
    elif spec.type == "number":
        widget = dbc.Input(
            id=param_input_id(spec.name),
            type="number",
            value=value,
        )
    elif spec.type == "date":
        widget = dcc.DatePickerSingle(
            id=param_input_id(spec.name),
            date=value,
        )
    else:  # "text" or fallback
        widget = dbc.Input(
            id=param_input_id(spec.name),
            type="text",
            value=value or "",
        )
    return html.Div([label, widget], className="mb-3")


def render_parameter_form(
    template: "CardTemplate", current_params: dict[str, Any] | None = None
) -> "Component":
    """Render the form skeleton for a template's parameter list.

    `current_params` is used when the form is being rerendered due to
    cascading `options_fn` changes so that user-entered values are preserved.
    """
    fields = [
        _field_component(p, current_params=current_params)
        for p in template.TEMPLATE_META.parameters
    ]
    if not fields:
        fields = [
            html.Div("This template takes no parameters.", className="text-muted")
        ]
    return html.Div(fields)


def _instantiate_entry(template: "CardTemplate", params: dict[str, Any]) -> Any:
    """Run instantiate(params) and tag the resulting card with a deterministic id.

    The card may already set its own id; we override it so two configurator entries
    with identical params resolve to the same id (idempotent Add).
    """
    card = template.instantiate(params)
    desired_id = card_id_for(template.TEMPLATE_META.id, params)
    meta = dict(card.CARD_META)
    meta["id"] = desired_id
    # Some teams may have used an immutable mapping; if so just leave it.
    try:
        card.CARD_META = meta  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass
    return card


def instantiate_working_list(
    working: list[dict[str, Any]], registry: "CardRegistry"
) -> list[Any]:
    """Resolve the working list entries to live Card objects.

    `working` is the JSON-serialisable list that lives in `dcc.Store`:
        [{"template_id": "kpi", "params": {...}}, ...]
    Unknown template IDs are skipped silently — they'll show up missing rather
    than crash the page.
    """
    cards: list[Any] = []
    for entry in working:
        try:
            tpl = registry.get_template(entry["template_id"])
        except KeyError:
            continue
        for params in fanout_params(tpl, entry.get("params", {})):
            cards.append(_instantiate_entry(tpl, params))
    return cards


def _render_card_tile(card: Any, context: dict) -> "Component":
    """Render a single working-list card as a tile with the ⋮ menu overlay.

    Returns a bare component (no column wrapper) — packing is the caller's job.
    """
    cid = card.CARD_META["id"]
    body = error_boundary(card, context)
    menu = dbc.DropdownMenu(
        label="⋮",
        children=[
            # Inject opt-in actions declared by the card (each item is {"id": ..., "label": ...})
            *[
                dbc.DropdownMenuItem(
                    a.get("label", a.get("id")),
                    id={
                        "type": "_cockpit_card_action",
                        "card_id": cid,
                        "action": a.get("id"),
                    },
                    n_clicks=0,
                )
                for a in card.CARD_META.get("actions", [])
            ],
            dbc.DropdownMenuItem(
                "Remove",
                id=remove_btn_id(cid),
                n_clicks=0,
            ),
        ],
        size="sm",
        color="link",
        align_end=True,
        toggle_style={
            "color": "#6c757d",
            "padding": "0 6px",
            "fontSize": "1.2rem",
            "lineHeight": "1",
            "border": "none",
            "background": "transparent",
            "boxShadow": "none",
        },
    )
    return html.Div(
        [
            html.Div(
                menu,
                style={
                    "position": "absolute",
                    "top": "4px",
                    "right": "4px",
                    "zIndex": 2,
                },
            ),
            body,
        ],
        style={"position": "relative"},
    )


def render_working_list(
    cards: list[Any], columns: int = 2, context: dict | None = None
) -> "Component":
    if context is None:
        context = {}
    if not cards:
        return html.Div(
            "No cards yet. Pick a template, set parameters, and click Add.",
            className="text-muted p-4",
        )
    tiles = [_render_card_tile(c, context) for c in cards]
    ids = [c.CARD_META["id"] for c in cards]
    return pack_grid(
        tiles,
        ids=ids,
        columns=columns,
        grid_id="_cockpit_cfg_grid",
    )


def render_configurator(
    page: "ConfiguratorPage", registry: "CardRegistry"
) -> "Component":
    """Initial server-side layout for a ConfiguratorPage. Callbacks fill in the rest."""
    available_templates = []
    for tid in page.template_ids:
        try:
            tpl = registry.get_template(tid)
        except KeyError:
            continue
        available_templates.append(tpl)

    if not available_templates:
        return html.Div(
            f"No templates registered for page {page.name!r}. "
            f"Expected: {page.template_ids}",
            className="text-warning p-4",
        )

    options = [
        {"label": t.TEMPLATE_META.title, "value": t.TEMPLATE_META.id}
        for t in available_templates
    ]
    initial_template = available_templates[0]

    sidebar = html.Div(
        [
            html.H6("Template", className="mb-2"),
            dcc.Dropdown(
                id=TEMPLATE_PICKER_ID,
                options=options,
                value=initial_template.TEMPLATE_META.id,
                clearable=False,
                className="mb-3",
            ),
            html.Div(render_parameter_form(initial_template), id=FORM_ID),
            html.Div(
                [
                    dbc.Button("Add", id=ADD_BTN_ID, color="primary", className="me-2"),
                    dbc.Button(
                        "Clear", id=CLEAR_BTN_ID, color="secondary", outline=True
                    ),
                ],
                className="mt-3",
            ),
            html.Div(id=STATUS_ID, className="text-muted small mt-2"),
        ],
        style={
            "width": "320px",
            "padding": "16px",
            "background": "#f8f9fa",
            "borderRight": "1px solid #dee2e6",
            "flexShrink": "0",
        },
    )

    main = html.Div(
        id=CARDS_PANE_ID,
        style={"flex": "1", "padding": "16px", "overflowY": "auto"},
        children=render_working_list([], columns=page.columns),
    )

    return html.Div(
        [
            dcc.Store(id=WORKING_LIST_STORE_ID, data=[], storage_type="session"),
            html.Div(
                [sidebar, main],
                style={"display": "flex", "minHeight": "60vh"},
            ),
        ]
    )


def register_configurator_callbacks(app: "dash.Dash", registry: "CardRegistry") -> None:
    """Wire all callbacks for ConfiguratorPage rendering. Idempotent: caller decides when to call."""
    from dash import ALL, Input, Output, State, callback_context, no_update

    @app.callback(
        Output(FORM_ID, "children"),
        Input(TEMPLATE_PICKER_ID, "value"),
        Input({"type": "_cockpit_cfg_param", "name": ALL}, "value"),
        State({"type": "_cockpit_cfg_param", "name": ALL}, "id"),
        prevent_initial_call=True,
    )
    def _swap_or_refresh_form(template_id, param_values, ids):
        """Handle both template swaps and parameter-change-driven form rerenders.

        - If the template picker triggered, render the template's empty form.
        - If parameter values triggered, call any `options_fn` with the current
          params and re-render the form so cascading selects update.
        """
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        trigger = ctx.triggered[0]["prop_id"]

        # Template picker changed
        if trigger.startswith(TEMPLATE_PICKER_ID):
            if not template_id:
                return no_update
            try:
                tpl = registry.get_template(template_id)
            except KeyError:
                return html.Div(
                    f"Unknown template: {template_id}", className="text-danger"
                )
            return render_parameter_form(tpl)

        # Parameter values changed
        try:
            tpl = registry.get_template(template_id)
        except Exception:
            return no_update
        params = {i["name"]: v for i, v in zip(ids, param_values, strict=False)}
        return render_parameter_form(tpl, current_params=params)

    @app.callback(
        Output(WORKING_LIST_STORE_ID, "data"),
        Output(STATUS_ID, "children"),
        Input(ADD_BTN_ID, "n_clicks"),
        Input(CLEAR_BTN_ID, "n_clicks"),
        Input({"type": "_cockpit_cfg_remove", "card_id": ALL}, "n_clicks"),
        State(TEMPLATE_PICKER_ID, "value"),
        State({"type": "_cockpit_cfg_param", "name": ALL}, "id"),
        State({"type": "_cockpit_cfg_param", "name": ALL}, "value"),
        State(WORKING_LIST_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def _mutate_working(
        add_clicks, clear_clicks, remove_clicks, template_id, ids, values, current
    ):
        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update
        trigger = ctx.triggered[0]["prop_id"]
        current = current or []

        if trigger.startswith(CLEAR_BTN_ID):
            return [], "Cleared."

        if trigger.startswith(ADD_BTN_ID):
            if not template_id:
                return no_update, "Pick a template first."
            try:
                tpl = registry.get_template(template_id)
            except KeyError:
                return no_update, f"Unknown template: {template_id}"
            params = {i["name"]: v for i, v in zip(ids, values, strict=False)}
            missing = [
                p.name
                for p in tpl.TEMPLATE_META.parameters
                if p.required and (params.get(p.name) in (None, "", []))
            ]
            if missing:
                return no_update, f"Missing required: {', '.join(missing)}"
            new_entry = {"template_id": template_id, "params": params}
            seen_ids = {card_id_for(e["template_id"], e["params"]) for e in current}
            new_id = card_id_for(template_id, params)
            if new_id in seen_ids:
                return no_update, "Already in working list."
            return [*current, new_entry], "Added."

        # Remove triggered
        import json as _json

        try:
            payload = _json.loads(trigger.rsplit(".", 1)[0])
            target = payload.get("card_id")
        except (ValueError, KeyError):
            return no_update, no_update
        if not target:
            return no_update, no_update
        # Filter out any entry whose canonical id matches (or whose fanout produced it)
        kept = []
        for entry in current:
            tpl_id = entry["template_id"]
            try:
                tpl = registry.get_template(tpl_id)
            except KeyError:
                kept.append(entry)
                continue
            ids_for_entry = {
                card_id_for(tpl_id, p) for p in fanout_params(tpl, entry["params"])
            }
            if target in ids_for_entry:
                continue
            kept.append(entry)
        return kept, "Removed."

    @app.callback(
        Output(CARDS_PANE_ID, "children"),
        Input(WORKING_LIST_STORE_ID, "data"),
    )
    def _render_pane(working):
        cards = instantiate_working_list(working or [], registry)
        return render_working_list(cards, columns=2)


def configurator_export_data(working: list[dict[str, Any]], registry: "CardRegistry"):
    """Build PageExportData for a configurator's live working list."""
    from dash_cockpit._export import CardExportEntry, PageExportData

    cards = instantiate_working_list(working or [], registry)
    entries = [CardExportEntry(meta=dict(c.CARD_META), card=c) for c in cards]
    return PageExportData(page_name="configurator", cards=entries, metadata={})
