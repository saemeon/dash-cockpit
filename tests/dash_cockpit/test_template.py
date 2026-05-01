from __future__ import annotations

import pytest
from dash import html

from dash_cockpit._registry import CardRegistry, RegistryError
from dash_cockpit._template import (
    CardTemplate,
    ParameterSpec,
    TemplateMeta,
    card_id_for,
    fanout_params,
)


def _meta(**overrides):
    base = {
        "id": "x",
        "title": "X",
        "team": "t",
        "description": "",
        "refresh_interval": 0,
        "category": "c",
    }
    base.update(overrides)
    return base


class _ConcreteCard:
    def __init__(self, params):
        self._params = params
        self.CARD_META = _meta(id=card_id_for("kpi", params), title=f"KPI {params}")

    def render(self, ctx):
        return html.Div(str(self._params))


class _KpiTemplate:
    TEMPLATE_META = TemplateMeta(
        id="kpi",
        title="KPI Lookup",
        team="finance",
        description="Pick a year and metric",
        category="finance",
        parameters=[
            ParameterSpec(name="year", label="Year", type="select", options=[2024, 2025]),
            ParameterSpec(name="metric", label="Metric", type="select", options=["revenue", "cost"]),
        ],
    )

    def instantiate(self, params):
        return _ConcreteCard(params)


def test_template_runtime_checkable():
    assert isinstance(_KpiTemplate(), CardTemplate)


def test_template_meta_fields():
    meta = _KpiTemplate.TEMPLATE_META
    assert meta.id == "kpi"
    assert meta.title == "KPI Lookup"
    assert len(meta.parameters) == 2
    assert meta.parameters[0].name == "year"


def test_card_id_deterministic():
    a = card_id_for("kpi", {"year": 2025, "metric": "revenue"})
    b = card_id_for("kpi", {"metric": "revenue", "year": 2025})  # order-insensitive
    c = card_id_for("kpi", {"year": 2024, "metric": "revenue"})
    assert a == b
    assert a != c
    assert a.startswith("kpi-")


def test_register_template():
    reg = CardRegistry()
    reg.register_template(_KpiTemplate())
    assert reg.all_template_ids() == ["kpi"]
    assert reg.get_template("kpi").TEMPLATE_META.id == "kpi"


def test_register_duplicate_template_raises():
    reg = CardRegistry()
    reg.register_template(_KpiTemplate())
    with pytest.raises(RegistryError, match="Duplicate template id"):
        reg.register_template(_KpiTemplate())


def test_get_unknown_template_raises():
    reg = CardRegistry()
    with pytest.raises(KeyError):
        reg.get_template("nope")


def test_load_package_with_templates_only():
    import sys
    import types

    mod = types.ModuleType("_fake_team_with_templates")
    mod.get_card_templates = lambda: [_KpiTemplate()]
    sys.modules["_fake_team_with_templates"] = mod
    try:
        reg = CardRegistry()
        ids = reg.load_package("_fake_team_with_templates")
        assert ids == []  # no static cards
        assert reg.all_template_ids() == ["kpi"]
    finally:
        del sys.modules["_fake_team_with_templates"]


def test_load_package_with_cards_and_templates(make_card):
    import sys
    import types

    mod = types.ModuleType("_fake_team_combo")
    mod.get_cards = lambda: [make_card("static")]
    mod.get_card_templates = lambda: [_KpiTemplate()]
    sys.modules["_fake_team_combo"] = mod
    try:
        reg = CardRegistry()
        ids = reg.load_package("_fake_team_combo")
        assert ids == ["static"]
        assert reg.all_template_ids() == ["kpi"]
    finally:
        del sys.modules["_fake_team_combo"]


def test_load_package_neither_raises():
    import sys
    import types

    mod = types.ModuleType("_fake_team_empty")
    sys.modules["_fake_team_empty"] = mod
    try:
        reg = CardRegistry()
        with pytest.raises(RegistryError, match="get_cards"):
            reg.load_package("_fake_team_empty")
    finally:
        del sys.modules["_fake_team_empty"]


def test_template_instantiate_returns_card():
    tpl = _KpiTemplate()
    card = tpl.instantiate({"year": 2025, "metric": "revenue"})
    assert hasattr(card, "CARD_META")
    assert card.CARD_META["id"].startswith("kpi-")


def test_fanout_no_multi_select():
    tpl = _KpiTemplate()
    out = fanout_params(tpl, {"year": 2025, "metric": "revenue"})
    assert out == [{"year": 2025, "metric": "revenue"}]


class _MultiTemplate:
    TEMPLATE_META = TemplateMeta(
        id="multi",
        title="Multi",
        team="t",
        description="",
        category="c",
        parameters=[
            ParameterSpec(name="year", label="Year", type="select", options=[2025]),
            ParameterSpec(
                name="level",
                label="Level",
                type="multi_select",
                options=["A", "B", "C"],
                default=[],
            ),
        ],
    )

    def instantiate(self, params):
        return _ConcreteCard(params)


def test_fanout_multi_select_expands():
    tpl = _MultiTemplate()
    out = fanout_params(tpl, {"year": 2025, "level": ["A", "B"]})
    assert len(out) == 2
    assert {p["level"] for p in out} == {"A", "B"}
    assert all(p["year"] == 2025 for p in out)


def test_fanout_empty_multi_select_yields_nothing():
    tpl = _MultiTemplate()
    assert fanout_params(tpl, {"year": 2025, "level": []}) == []
