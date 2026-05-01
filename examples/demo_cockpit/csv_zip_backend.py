"""Demo export backend: bundles every TabularCard's tables into a zip of CSVs.

Trivial reference implementation showing how an ExportBackend consumes
PageExportData. A production backend (Word/PDF/Excel) would do the same
dispatch on the protocol facets exposed by each card.
"""

from __future__ import annotations

import io
import zipfile

from dash_cockpit import PageExportData, TabularCard


class CSVZipBackend:
    """Writes every TabularCard's tables into a single zip of CSV files."""

    def export(self, page_data: PageExportData) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            wrote_anything = False
            for entry in page_data.cards:
                card = entry.card
                if not isinstance(card, TabularCard):
                    continue
                tables = card.get_tables()
                cid = entry.meta["id"]
                for name, df in tables.items():
                    arcname = f"{cid}/{name}.csv"
                    zf.writestr(arcname, df.to_csv(index=False))
                    wrote_anything = True
            if not wrote_anything:
                zf.writestr("README.txt", "No tabular cards on this page.\n")
        return buf.getvalue()

    def filename_for(self, page_name: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (page_name or "page"))
        return f"{safe}.zip"
