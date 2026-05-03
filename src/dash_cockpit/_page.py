"""Page types — the three ways a card list ends up on screen."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TeamPage:
    """A team-curated page: a fixed, ordered list of cards.

    The most common page type. A team author hard-codes which cards appear
    and in what order; users can drag/resize at runtime but cannot add or
    remove cards.

    Parameters
    ----------
    name : str
        Page title shown in the sidebar.
    card_ids : list[str]
        Cards rendered in declaration order, wrapping at ``columns``. IDs
        must resolve via the registry; unknown IDs render a yellow warning
        tile rather than breaking the page.
    id : str, optional
        Stable URL slug for this page. When empty, the cockpit derives one
        from ``name``. Set explicitly to keep bookmarks working when ``name``
        changes. By default ``""``.
    team : str
        Owning team's machine name. Informational; not used for rendering.
        By default ``""``.
    columns : int
        Grid width in widget units. Each card defaults to ``(1, 1)``;
        cards declaring ``size=(2, 1)`` span two columns. By default ``12``.
    grid_columns : int
        Reserved for future use. By default ``0`` (use ``columns``).

    Examples
    --------
    >>> TeamPage(
    ...     name="Finance Overview",
    ...     card_ids=["revenue_trend", "cash_position", "margin"],
    ...     team="finance",
    ...     columns=3,
    ... )
    """

    name: str
    card_ids: list[str]
    id: str = ""
    team: str = ""
    columns: int = 12
    grid_columns: int = 0


@dataclass
class UserPage:
    """A user-defined page laid out as explicit rows.

    Unlike ``TeamPage``, the layout is a 2D structure — each inner list is
    one row, and cards in a row equal-divide its width. Suited to "saved
    presets" rather than runtime composition.

    Parameters
    ----------
    name : str
        Page title shown in the sidebar.
    layout : list[list[str]]
        Rows of card IDs. ``[["a", "b"], ["c"]]`` renders ``a`` and ``b``
        side-by-side on row 1, ``c`` full-width on row 2.
    id : str, optional
        Stable URL slug for this page. When empty, the cockpit derives one
        from ``name``. By default ``""``.

    Examples
    --------
    >>> UserPage(
    ...     name="My View",
    ...     layout=[["revenue_trend", "margin"], ["risk_exposure"]],
    ... )
    """

    name: str
    layout: list[list[str]]
    id: str = ""


@dataclass
class ConfiguratorPage:
    """A user-built page assembled at runtime from card templates.

    The user picks a template, fills in parameters, clicks "Add", and the
    cockpit instantiates a card and appends it to the working list. State
    lives in browser-side ``dcc.Store`` — there are no static ``card_ids``.

    Parameters
    ----------
    name : str
        Page title shown in the sidebar.
    template_ids : list[str]
        Templates the user is allowed to pick from. Each must be registered
        via ``CardRegistry.register_template``.
    initial_card_ids : list[str], optional
        Static cards always shown above the configurator. Useful for
        "always-on" KPIs alongside user-built ones. By default ``[]``.
    columns : int
        Grid width for the working list. By default ``12``.
    id : str, optional
        Stable URL slug for this page. When empty, the cockpit derives one
        from ``name``. By default ``""``.

    Examples
    --------
    >>> ConfiguratorPage(
    ...     name="KPI Builder",
    ...     template_ids=["kpi_lookup"],
    ...     columns=3,
    ... )
    """

    name: str
    template_ids: list[str]
    initial_card_ids: list[str] = field(default_factory=list)
    columns: int = 12
    id: str = ""


Page = TeamPage | UserPage | ConfiguratorPage
"""Union of all concrete page types accepted by ``CockpitApp``."""


def page_card_ids(page: Page) -> list[str]:
    """Return the static card IDs referenced by a page.

    For ``ConfiguratorPage`` this returns only ``initial_card_ids`` — the
    dynamically-instantiated working list lives in browser state and is not
    visible from the server.

    Parameters
    ----------
    page : Page
        Any concrete page type.

    Returns
    -------
    list[str]
        Flat list of card IDs in declaration order.

    Examples
    --------
    >>> page_card_ids(TeamPage(name="X", card_ids=["a", "b"]))
    ['a', 'b']
    >>> page_card_ids(UserPage(name="X", layout=[["a", "b"], ["c"]]))
    ['a', 'b', 'c']
    """
    if isinstance(page, TeamPage):
        return list(page.card_ids)
    if isinstance(page, ConfiguratorPage):
        return list(page.initial_card_ids)
    return [cid for row in page.layout for cid in row]
