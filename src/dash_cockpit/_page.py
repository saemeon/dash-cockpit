from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TeamPage:
    name: str
    card_ids: list[str]
    team: str = ""
    columns: int = 2  # legacy: cards per row when no card declares a size
    grid_columns: int = 0  # widget-grid units per row (0 = use `columns`)


@dataclass
class UserPage:
    name: str
    layout: list[list[str]]  # explicit rows of card_id lists


@dataclass
class ConfiguratorPage:
    """User-assembled page: pick a template, parametrize, append to working list.

    The working list lives in browser state (a session `dcc.Store`) — no static
    `card_ids`. The page only declares which templates the user is allowed to
    pick from.
    """

    name: str
    template_ids: list[str]
    initial_card_ids: list[str] = field(default_factory=list)
    columns: int = 2


Page = TeamPage | UserPage | ConfiguratorPage


def page_card_ids(page: Page) -> list[str]:
    """Flat list of static card IDs referenced by a page.

    For ConfiguratorPage this returns only `initial_card_ids` — the dynamically
    instantiated working list lives in browser state and is not visible here.
    """
    if isinstance(page, TeamPage):
        return list(page.card_ids)
    if isinstance(page, ConfiguratorPage):
        return list(page.initial_card_ids)
    return [cid for row in page.layout for cid in row]
