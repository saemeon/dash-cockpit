from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class TabularCard(Protocol):
    """Card that exposes tabular data for Excel/CSV export."""

    def get_tables(self) -> dict[str, "pd.DataFrame"]: ...


@runtime_checkable
class DocumentCard(Protocol):
    """Card that renders itself into a document backend (Word/PDF/HTML)."""

    def render_into_document(self, backend: Any) -> None: ...


@runtime_checkable
class ChartCard(Protocol):
    """Card that exposes its chart as raw bytes (SVG/PNG)."""

    def get_chart(self, format: str) -> bytes: ...

    def chart_name(self) -> str: ...


@dataclass(frozen=True)
class CardExportEntry:
    """One card's metadata + the card object, ready for an export backend."""

    meta: dict[str, Any]
    card: Any  # the card object; backends inspect its protocols


@dataclass(frozen=True)
class PageExportData:
    """Snapshot of a page passed to an export backend."""

    page_name: str
    cards: list[CardExportEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExportBackend(Protocol):
    """Anything that can turn a PageExportData into bytes (Excel/PDF/Word/zip/...)."""

    def export(self, page_data: PageExportData) -> bytes: ...


def classify_card(card: Any) -> set[str]:
    """Return the set of export facets a card supports: {"tabular", "document", "chart"}."""
    facets = set()
    if isinstance(card, TabularCard):
        facets.add("tabular")
    if isinstance(card, DocumentCard):
        facets.add("document")
    if isinstance(card, ChartCard):
        facets.add("chart")
    return facets


def build_page_export_data(page, registry, page_metadata: dict | None = None) -> PageExportData:
    """Snapshot a page into a PageExportData payload for an ExportBackend.

    Resolves card IDs to (meta, card_obj) pairs via the registry. Unknown IDs are skipped.
    """
    from dash_cockpit._page import page_card_ids

    entries: list[CardExportEntry] = []
    for cid in page_card_ids(page):
        try:
            entry = registry.get(cid)
        except KeyError:
            continue
        # The registry stores {"render": fn, "meta": ...}. We need the card object itself
        # for protocol checks, so we look it up via the registry's internal store.
        card_obj = registry._registry[cid].get("card", entry["render"])
        entries.append(CardExportEntry(meta=dict(entry["meta"]), card=card_obj))

    return PageExportData(
        page_name=getattr(page, "name", ""),
        cards=entries,
        metadata=dict(page_metadata or {}),
    )


def export_page(page, registry, backend: ExportBackend, page_metadata: dict | None = None) -> bytes:
    """Snapshot the page and hand it to the export backend."""
    data = build_page_export_data(page, registry, page_metadata=page_metadata)
    return backend.export(data)
