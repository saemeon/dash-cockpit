"""Demo cockpit wiring two team packages into a single Dash app.

Run from the examples/demo_cockpit/ directory:
    python app.py

The teams (team_finance, team_ops) live as sibling folders. We add the current
directory to sys.path so they import as top-level packages, mirroring how a
production deployment installs them as proper distributions.
"""

import sys
from pathlib import Path

# Add this directory to sys.path so team_finance / team_ops are importable
sys.path.insert(0, str(Path(__file__).parent))

from csv_zip_backend import CSVZipBackend  # noqa: E402

from dash_cockpit import (  # noqa: E402
    CardRegistry,
    CockpitApp,
    ConfiguratorPage,
    TeamPage,
    UserPage,
)


def build_app() -> CockpitApp:
    registry = CardRegistry()
    registry.load_packages(["team_finance", "team_ops"])

    pages = [
        TeamPage(
            name="Finance Overview",
            card_ids=["revenue_trend", "cash_position"],
            team="finance",
            columns=2,
        ),
        TeamPage(
            name="Operations",
            card_ids=["headcount", "ticket_volume", "broken_card"],
            team="ops",
            columns=2,
        ),
        UserPage(
            name="Executive Mix",
            layout=[
                ["revenue_trend", "headcount"],
                ["cash_position", "ticket_volume"],
            ],
        ),
        ConfiguratorPage(
            name="KPI Builder",
            template_ids=["kpi_lookup"],
            columns=2,
        ),
    ]

    print(f"Loaded {len(registry)} cards: {registry.all_ids()}")
    return CockpitApp(
        registry=registry,
        pages=pages,
        title="DEMO Cockpit",
        export_backends={"CSV (zip)": CSVZipBackend()},
    )


if __name__ == "__main__":
    app = build_app()
    app.run(debug=True, port=8019)
