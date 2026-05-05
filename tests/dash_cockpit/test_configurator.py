from __future__ import annotations

from dash import html

from dash_cockpit._configurator import (
    CARDS_PANE_ID,
    FORM_ID,
    TEMPLATE_PICKER_ID,
    WORKING_LIST_STORE_ID,
    _coerce_param,
    _params_from_callback,
    configurator_export_data,
    instantiate_working_list,
    render_configurator,
    render_parameter_form,
    render_working_list,
)
from dash_cockpit._layout import render_page
from dash_cockpit._page import ConfiguratorPage
from dash_cockpit._registry import CardRegistry
from dash_cockpit._template import ParameterSpec, TemplateMeta, card_id_for


class _ConcreteCard:
    def __init__(self, params):
        self._params = params
        self.CARD_META = {
            "id": "placeholder",
            "title": f"KPI {params}",
            "team": "finance",
            "description": "",
            "refresh_interval": 0,
            "category": "finance",
        }

    def render(self, ctx):
        return html.Div(str(self._params))


class _KpiTemplate:
    TEMPLATE_META = TemplateMeta(
        id="kpi",
        title="KPI",
        team="finance",
        description="",
        category="finance",
        parameters=[
            ParameterSpec("year", "Year", "select", options=[2024, 2025], default=2025),
            ParameterSpec(
                "metric", "Metric", "select", options=["rev", "cost"], default="rev"
            ),
        ],
    )

    def instantiate(self, params):
        return _ConcreteCard(params)


class _MultiTemplate:
    TEMPLATE_META = TemplateMeta(
        id="multi",
        title="Multi",
        team="finance",
        description="",
        category="finance",
        parameters=[
            ParameterSpec("year", "Year", "select", options=[2025], default=2025),
            ParameterSpec(
                "level",
                "Level",
                "multi_select",
                options=["A", "B"],
                default=[],
            ),
        ],
    )

    def instantiate(self, params):
        return _ConcreteCard(params)


def _make_registry(*templates):
    reg = CardRegistry()
    for t in templates:
        reg.register_template(t)
    return reg


def test_render_parameter_form_has_one_div_per_field():
    rendered = render_parameter_form(_KpiTemplate())
    s = str(rendered)
    assert "Year" in s
    assert "Metric" in s


def test_render_parameter_form_no_params():
    class _Empty:
        TEMPLATE_META = TemplateMeta(
            id="e", title="E", team="t", description="", category="c", parameters=[]
        )

        def instantiate(self, p):
            return None

    rendered = render_parameter_form(_Empty())
    assert "no parameters" in str(rendered).lower()


def test_render_configurator_includes_store_and_picker():
    reg = _make_registry(_KpiTemplate())
    page = ConfiguratorPage(name="Configurator", template_ids=["kpi"])
    rendered = render_configurator(page, reg)
    s = str(rendered)
    assert TEMPLATE_PICKER_ID in s
    assert FORM_ID in s
    assert WORKING_LIST_STORE_ID in s
    assert CARDS_PANE_ID in s


def test_render_configurator_includes_share_button():
    from dash_cockpit._configurator import SHARE_BTN_ID

    reg = _make_registry(_KpiTemplate())
    page = ConfiguratorPage(name="Configurator", template_ids=["kpi"])
    rendered = render_configurator(page, reg)
    s = str(rendered)
    assert SHARE_BTN_ID in s
    assert "Share link" in s


def test_render_configurator_unknown_templates_warning():
    reg = CardRegistry()
    page = ConfiguratorPage(name="Empty", template_ids=["does_not_exist"])
    rendered = render_configurator(page, reg)
    assert "No templates registered" in str(rendered)


def test_render_configurator_partial_unknown_templates():
    reg = _make_registry(_KpiTemplate())
    page = ConfiguratorPage(name="Mix", template_ids=["kpi", "ghost"])
    rendered = render_configurator(page, reg)
    s = str(rendered)
    assert "kpi" in s
    # Ghost template should be silently dropped, not crash
    assert "No templates registered" not in s


def test_render_page_dispatches_to_configurator():
    reg = _make_registry(_KpiTemplate())
    page = ConfiguratorPage(name="C", template_ids=["kpi"])
    out = render_page(page, reg)
    assert WORKING_LIST_STORE_ID in str(out)


def test_instantiate_working_list_simple():
    reg = _make_registry(_KpiTemplate())
    cards = instantiate_working_list(
        [{"template_id": "kpi", "params": {"year": 2025, "metric": "rev"}}],
        reg,
    )
    assert len(cards) == 1
    assert cards[0].CARD_META["id"] == card_id_for(
        "kpi", {"year": 2025, "metric": "rev"}
    )


def test_instantiate_working_list_skips_unknown_template():
    reg = _make_registry(_KpiTemplate())
    cards = instantiate_working_list(
        [
            {"template_id": "kpi", "params": {"year": 2025, "metric": "rev"}},
            {"template_id": "ghost", "params": {}},
        ],
        reg,
    )
    assert len(cards) == 1


def test_instantiate_working_list_multi_select_fanout():
    reg = _make_registry(_MultiTemplate())
    cards = instantiate_working_list(
        [{"template_id": "multi", "params": {"year": 2025, "level": ["A", "B"]}}],
        reg,
    )
    assert len(cards) == 2
    ids = {c.CARD_META["id"] for c in cards}
    assert len(ids) == 2  # distinct ids per fanned-out value


def test_render_working_list_empty_placeholder():
    rendered = render_working_list([])
    assert "No cards yet" in str(rendered)


def test_render_working_list_renders_cards():
    reg = _make_registry(_KpiTemplate())
    cards = instantiate_working_list(
        [{"template_id": "kpi", "params": {"year": 2025, "metric": "rev"}}],
        reg,
    )
    rendered = render_working_list(cards, columns=2)
    assert "_cockpit_cfg_remove" in str(rendered)


def test_configurator_export_data_builds_entries():
    reg = _make_registry(_KpiTemplate())
    data = configurator_export_data(
        [{"template_id": "kpi", "params": {"year": 2025, "metric": "rev"}}],
        reg,
    )
    assert data.page_name == "configurator"
    assert len(data.cards) == 1
    assert data.cards[0].meta["id"].startswith("kpi-")


def test_configurator_export_data_empty():
    reg = _make_registry(_KpiTemplate())
    data = configurator_export_data([], reg)
    assert data.cards == []


def test_options_fn_applies_based_on_current_params():
    class _CascadeTemplate:
        TEMPLATE_META = TemplateMeta(
            id="cascade",
            title="Cascade",
            team="finance",
            description="",
            category="finance",
            parameters=[
                ParameterSpec(
                    "year", "Year", "select", options=[2024, 2025], default=2025
                ),
                ParameterSpec(
                    "metric",
                    "Metric",
                    "select",
                    options=None,
                    options_fn=lambda params: (
                        ["rev"] if params.get("year") == 2025 else ["cost"]
                    ),
                ),
            ],
        )

        def instantiate(self, params):
            return _ConcreteCard(params)

    # When year == 2025 the metric options should be ['rev']
    rendered = render_parameter_form(_CascadeTemplate(), current_params={"year": 2025})
    assert "rev" in str(rendered)

    # When year == 2024 the metric options should be ['cost']
    rendered2 = render_parameter_form(_CascadeTemplate(), current_params={"year": 2024})
    assert "cost" in str(rendered2)


def test_card_actions_show_in_tile_menu():
    class _ActionCard:
        def __init__(self, p):
            self._p = p
            self.CARD_META = {
                "id": "act1",
                "title": "Act",
                "team": "t",
                "description": "",
                "refresh_interval": 0,
                "category": "c",
                "actions": [
                    {"id": "refresh", "label": "Refresh"},
                    {"id": "settings", "label": "Settings"},
                ],
            }

        def render(self, ctx):
            return html.Div("ok")

    class _ActionTemplate:
        TEMPLATE_META = TemplateMeta(
            id="act_tpl",
            title="A",
            team="t",
            description="",
            category="c",
            parameters=[],
        )

        def instantiate(self, params):
            return _ActionCard(params)

    reg = _make_registry(_ActionTemplate())
    cards = instantiate_working_list(
        [
            {"template_id": "act_tpl", "params": {}},
        ],
        reg,
    )
    rendered = render_working_list(cards)
    # The menu should include the action labels
    assert "Refresh" in str(rendered)
    assert "Settings" in str(rendered)


# ---------------------------------------------------------------------------
# _coerce_param + _params_from_callback — round-trip from dmc string to spec type
# ---------------------------------------------------------------------------


def test_coerce_param_select_int_round_trip():
    spec = ParameterSpec(
        name="year", label="Year", type="select", options=[2024, 2025], default=2025
    )
    assert _coerce_param(spec, "2025") == 2025
    assert _coerce_param(spec, "2024") == 2024
    # Unknown value passes through (rare race during template swap).
    assert _coerce_param(spec, "9999") == "9999"


def test_coerce_param_select_string_pass_through():
    spec = ParameterSpec(
        name="metric",
        label="Metric",
        type="select",
        options=["revenue", "ebitda"],
        default="revenue",
    )
    assert _coerce_param(spec, "revenue") == "revenue"


def test_coerce_param_multi_select_int_round_trip():
    spec = ParameterSpec(
        name="years",
        label="Years",
        type="multi_select",
        options=[2024, 2025, 2026],
        default=[],
    )
    assert _coerce_param(spec, ["2024", "2026"]) == [2024, 2026]


def test_coerce_param_multi_select_unknown_pass_through():
    spec = ParameterSpec(
        name="years",
        label="Years",
        type="multi_select",
        options=[2024, 2025],
        default=[],
    )
    # Mix of known and unknown values — knowns coerce, unknowns pass.
    assert _coerce_param(spec, ["2025", "stale"]) == [2025, "stale"]


def test_coerce_param_number_int_when_integral():
    spec = ParameterSpec(name="n", label="N", type="number", default=10)
    assert _coerce_param(spec, "10") == 10
    assert _coerce_param(spec, 10) == 10


def test_coerce_param_number_float_when_not_integral():
    spec = ParameterSpec(name="r", label="Rate", type="number", default=0.5)
    assert _coerce_param(spec, "1.5") == 1.5


def test_coerce_param_number_garbage_passes_through():
    spec = ParameterSpec(name="n", label="N", type="number", default=0)
    assert _coerce_param(spec, "not-a-number") == "not-a-number"


def test_coerce_param_text_pass_through():
    spec = ParameterSpec(name="title", label="Title", type="text", default="")
    assert _coerce_param(spec, "hello") == "hello"


def test_coerce_param_none_pass_through():
    spec = ParameterSpec(
        name="year", label="Year", type="select", options=[2024, 2025]
    )
    assert _coerce_param(spec, None) is None
    assert _coerce_param(spec, "") == ""


def test_params_from_callback_pairs_ids_and_coerces():
    template = _KpiTemplate()
    ids = [{"name": "year"}, {"name": "metric"}, {"name": "division"}]
    values = ["2025", "revenue", ["EMEA", "APAC"]]
    out = _params_from_callback(template, ids, values)
    # year coerced int (matches options=[2024, 2025])
    assert out["year"] == 2025
    # metric stays string (matches options=["revenue", "ebitda"])
    assert out["metric"] == "revenue"
    # division (multi_select) stays list of strings
    assert out["division"] == ["EMEA", "APAC"]


def test_params_from_callback_unknown_name_passes_through():
    template = _KpiTemplate()
    ids = [{"name": "year"}, {"name": "ghost"}]
    values = ["2024", "raw"]
    out = _params_from_callback(template, ids, values)
    assert out == {"year": 2024, "ghost": "raw"}
