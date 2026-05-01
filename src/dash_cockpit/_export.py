"""Opt-in export protocols for cards and the page-level export pipeline.

A card chooses which export facets to support by implementing one or more
of :class:`TabularCard`, :class:`DocumentCard`, :class:`ChartCard`. The
cockpit inspects each card via ``isinstance``  and hands a snapshot
(:class:`PageExportData`) to a backend chosen by the user.

The protocols are decoupled from any concrete file format: backends decide
what to do with the cards they recognise (e.g. zip CSVs from
:class:`TabularCard`, write a Word document from :class:`DocumentCard`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class TabularCard(Protocol):
    """Card that exposes one or more named tables for tabular export.

    Returns a mapping of ``{sheet_name: DataFrame}`` so a single card can
    contribute several sheets to e.g. an Excel workbook or zip of CSVs.
    """

    def get_tables(self) -> dict[str, pd.DataFrame]:
        """Return the card's tables keyed by sheet/file name."""
        ...


@runtime_checkable
class DocumentCard(Protocol):
    """Card that knows how to render itself into a document backend.

    The card receives a backend-specific writer (e.g. a ``python-docx``
    document, a Typst section builder) and writes to it directly. This
    keeps formatting decisions inside the card.
    """

    def render_into_document(self, backend: Any) -> None:
        """Append this card's content to the document backend in place."""
        ...


@runtime_checkable
class ChartCard(Protocol):
    """Card that exposes its visual as raw bytes (SVG/PNG/...)."""

    def get_chart(self, format: str) -> bytes:
        """Return the chart bytes in the requested format (e.g. ``"svg"``)."""
        ...

    def chart_name(self) -> str:
        """Return the file-safe base name to use when saving the chart."""
        ...


@dataclass(frozen=True)
class CardExportEntry:
    """One card's export-time payload: its metadata plus the original object.

    Backends receive a list of these and inspect each ``card`` via the
    runtime-checkable export protocols (:class:`TabularCard` etc.) to decide
    what to extract.

    Parameters
    ----------
    meta : dict[str, Any]
        Snapshot of the card's ``CARD_META`` (a plain dict, safe to mutate).
    card : Any
        The card object itself, used for protocol-based dispatch in backends.
    """

    meta: dict[str, Any]
    card: Any


@dataclass(frozen=True)
class PageExportData:
    """Snapshot of one page handed to an :class:`ExportBackend`.

    Parameters
    ----------
    page_name : str
        Name of the source page (e.g. ``"Finance Overview"``). Backends use
        this for filenames and document titles.
    cards : list[CardExportEntry]
        Cards on the page, in declaration order. Empty list is valid — the
        backend decides whether that's an error.
    metadata : dict[str, Any]
        Free-form context (e.g. ``{"as_of": "2026-05-01"}``). Backends may
        ignore.
    """

    page_name: str
    cards: list[CardExportEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExportBackend(Protocol):
    """Anything that turns a :class:`PageExportData` into raw bytes.

    Backends pick which facets they care about. A CSV backend looks at
    :class:`TabularCard` cards only and produces a zip; a Word backend
    visits :class:`DocumentCard` cards in order; a PDF backend may combine
    both. The cockpit does not validate compatibility — backends are
    expected to handle absent facets gracefully.

    Notes
    -----
    Backends may optionally implement ``filename_for(page_name) -> str``;
    the cockpit will use it for download filenames if present.
    """

    def export(self, page_data: PageExportData) -> bytes:
        """Serialise the page snapshot to bytes ready for download."""
        ...


def classify_card(card: Any) -> set[str]:
    """Return the set of export facets a card supports.

    Parameters
    ----------
    card : Any
        Any object — typically a registered card.

    Returns
    -------
    set[str]
        Subset of ``{"tabular", "document", "chart"}`` based on which
        protocols ``card`` satisfies via runtime ``isinstance`` checks.

    Examples
    --------
    >>> classify_card(card_with_get_tables)
    {'tabular'}
    """
    facets = set()
    if isinstance(card, TabularCard):
        facets.add("tabular")
    if isinstance(card, DocumentCard):
        facets.add("document")
    if isinstance(card, ChartCard):
        facets.add("chart")
    return facets


def build_page_export_data(
    page, registry, page_metadata: dict | None = None
) -> PageExportData:
    """Snapshot a page into a :class:`PageExportData` for an export backend.

    Resolves card IDs via the registry, copies metadata, and packs each
    card object so backends can dispatch on the export protocols.

    Parameters
    ----------
    page : Page
        Any concrete page type (``TeamPage``, ``UserPage``, ``ConfiguratorPage``).
        For ``ConfiguratorPage`` only the static ``initial_card_ids`` are
        included — the live working list comes through a separate path.
    registry : CardRegistry
        Source of truth for card resolution. Unknown IDs are silently
        skipped.
    page_metadata : dict, optional
        Extra context attached to the snapshot. By default ``None``.

    Returns
    -------
    PageExportData
        Ready to hand to an :class:`ExportBackend`.
    """
    from dash_cockpit._page import page_card_ids

    entries: list[CardExportEntry] = []
    for cid in page_card_ids(page):
        try:
            entry = registry.get(cid)
        except KeyError:
            continue
        card_obj = registry._registry[cid].get("card", entry["render"])
        entries.append(CardExportEntry(meta=dict(entry["meta"]), card=card_obj))

    return PageExportData(
        page_name=getattr(page, "name", ""),
        cards=entries,
        metadata=dict(page_metadata or {}),
    )


def export_page(
    page, registry, backend: ExportBackend, page_metadata: dict | None = None
) -> bytes:
    """Snapshot a page and run the chosen export backend over it.

    Convenience wrapper for ``backend.export(build_page_export_data(...))``.

    Parameters
    ----------
    page : Page
        The page to export.
    registry : CardRegistry
        Source of truth for card resolution.
    backend : ExportBackend
        Format implementation that does the actual serialisation.
    page_metadata : dict, optional
        Extra context attached to the snapshot. By default ``None``.

    Returns
    -------
    bytes
        Whatever the backend produced — opaque to the cockpit.
    """
    data = build_page_export_data(page, registry, page_metadata=page_metadata)
    return backend.export(data)
