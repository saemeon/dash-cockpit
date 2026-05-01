from __future__ import annotations

import pandas as pd
from dash import html

from dash_cockpit._export import (
    ChartCard,
    DocumentCard,
    ExportBackend,
    PageExportData,
    TabularCard,
    build_page_export_data,
    classify_card,
    export_page,
)
from dash_cockpit._page import TeamPage, UserPage
from dash_cockpit._registry import CardRegistry


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


class _PlainCard:
    CARD_META = _meta(id="plain")

    def render(self, ctx):
        return html.Div("plain")


class _TabCard:
    CARD_META = _meta(id="tab")

    def render(self, ctx):
        return html.Div("tab")

    def get_tables(self):
        return {"main": pd.DataFrame({"a": [1, 2]})}


class _DocCard:
    CARD_META = _meta(id="doc")

    def render(self, ctx):
        return html.Div("doc")

    def render_into_document(self, backend):
        backend.append("doc rendered")


class _ChartishCard:
    CARD_META = _meta(id="chart")

    def render(self, ctx):
        return html.Div("chart")

    def get_chart(self, format: str) -> bytes:
        return b"<svg/>" if format == "svg" else b"PNG"

    def chart_name(self) -> str:
        return "chart-1"


def test_classify_plain_card():
    assert classify_card(_PlainCard()) == set()


def test_classify_tabular():
    assert "tabular" in classify_card(_TabCard())


def test_classify_document():
    assert "document" in classify_card(_DocCard())


def test_classify_chart():
    assert "chart" in classify_card(_ChartishCard())


def test_protocols_runtime_checkable():
    assert isinstance(_TabCard(), TabularCard)
    assert isinstance(_DocCard(), DocumentCard)
    assert isinstance(_ChartishCard(), ChartCard)
    assert not isinstance(_PlainCard(), TabularCard)
    assert not isinstance(_PlainCard(), DocumentCard)
    assert not isinstance(_PlainCard(), ChartCard)


def test_build_page_export_data_team_page():
    reg = CardRegistry()
    reg.register(_PlainCard())
    reg.register(_TabCard())
    page = TeamPage(name="P", card_ids=["plain", "tab"])
    data = build_page_export_data(page, reg)
    assert isinstance(data, PageExportData)
    assert data.page_name == "P"
    assert [e.meta["id"] for e in data.cards] == ["plain", "tab"]
    assert isinstance(data.cards[1].card, _TabCard)


def test_build_page_export_data_user_page_skips_unknown():
    reg = CardRegistry()
    reg.register(_PlainCard())
    page = UserPage(name="U", layout=[["plain"], ["nope"]])
    data = build_page_export_data(page, reg)
    assert [e.meta["id"] for e in data.cards] == ["plain"]


def test_build_page_export_data_metadata_passthrough():
    reg = CardRegistry()
    reg.register(_PlainCard())
    page = TeamPage(name="P", card_ids=["plain"])
    data = build_page_export_data(page, reg, page_metadata={"author": "sn"})
    assert data.metadata == {"author": "sn"}


class _StubBackend:
    def __init__(self):
        self.last: PageExportData | None = None

    def export(self, page_data: PageExportData) -> bytes:
        self.last = page_data
        return b"OK:" + page_data.page_name.encode()


def test_export_page_dispatch():
    reg = CardRegistry()
    reg.register(_TabCard())
    reg.register(_DocCard())
    page = TeamPage(name="report", card_ids=["tab", "doc"])
    backend = _StubBackend()
    out = export_page(page, reg, backend)
    assert out == b"OK:report"
    assert backend.last is not None
    assert [e.meta["id"] for e in backend.last.cards] == ["tab", "doc"]


def test_export_backend_protocol():
    assert isinstance(_StubBackend(), ExportBackend)
