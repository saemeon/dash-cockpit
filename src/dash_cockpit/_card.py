"""Card protocol — the atomic unit of insight a team publishes to the cockpit.

Note: this module deliberately does not use ``from __future__ import annotations``
because :class:`TypedDict` needs ``NotRequired`` to evaluate at class-creation
time so that ``__required_keys__`` is correct.
"""

from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from dash.development.base_component import Component


class CardMeta(TypedDict):
    """Metadata every card must declare on its ``CARD_META`` attribute.

    The cockpit reads this dict to register the card, route it to a page,
    surface it in menus, and decide its grid footprint. All required fields
    are validated at registration time; missing fields raise ``RegistryError``.

    Parameters
    ----------
    id : str
        Stable, globally-unique identifier. Used in URL paths, page card lists,
        and as the React key for layout persistence. Cards must keep the same
        id across deploys, otherwise saved layouts break.
    title : str
        Human-readable title shown above the card.
    team : str
        Owning team's machine name (e.g. ``"finance"``). Used by
        ``CardRegistry.by_team`` for filtering.
    description : str
        Short prose description for menus and tooltips.
    refresh_interval : int
        Auto-refresh cadence in seconds. ``0`` disables auto-refresh.
        Currently informational only — auto-refresh wiring is not yet
        implemented (see Phase 3 in the design doc).
    category : str
        Free-form category tag for grouping (e.g. ``"finance"``, ``"ops"``).
    size : tuple[int, int], optional
        Initial widget size in grid units, as ``(width, height)``. Defaults to
        ``(1, 1)``. A 4-column page gives a ``(2, 1)`` card half the width.
        Users can drag/resize at runtime; the new size is persisted in
        localStorage.
    actions : list[dict], optional
        Per-card menu actions. Each entry is a mapping with ``id`` and
        ``label`` keys; the cockpit renders them in the ⋮ dropdown and emits
        pattern-matching callback events when clicked. The team app is
        responsible for handling those events.

    Examples
    --------
    >>> CARD_META: CardMeta = {
    ...     "id": "revenue_trend",
    ...     "title": "Revenue Trend",
    ...     "team": "finance",
    ...     "description": "Monthly revenue development",
    ...     "refresh_interval": 300,
    ...     "category": "finance",
    ...     "size": (2, 1),
    ... }
    """

    id: str
    title: str
    team: str
    description: str
    refresh_interval: int
    category: str
    size: NotRequired[tuple[int, int]]
    actions: NotRequired[list[dict]]


@runtime_checkable
class Card(Protocol):
    """Protocol every cockpit card must satisfy.

    A card is the atomic unit of insight: a self-contained renderer plus its
    metadata. It must NOT depend on other cards or assume global state — the
    cockpit treats each card as an isolated widget (see the iOS-widget mental
    model in ``CLAUDE.md``).

    Attributes
    ----------
    CARD_META : CardMeta
        Required class- or instance-level dict. Keys are validated when the
        card is registered.

    Notes
    -----
    Use ``isinstance(obj, Card)`` to runtime-check whether an object satisfies
    the protocol — ``runtime_checkable`` is set.

    Cards must render fully on their own. They may fetch data, call services,
    or perform aggregation, but must NOT read from other cards or share state.

    Examples
    --------
    A minimal card as a plain object::

        from types import SimpleNamespace
        from dash import html

        revenue_card = SimpleNamespace(
            CARD_META={
                "id": "revenue", "title": "Revenue",
                "team": "finance", "description": "Q4 revenue",
                "refresh_interval": 0, "category": "finance",
            },
            render=lambda ctx: html.Div("$12.4M"),
        )
    """

    CARD_META: CardMeta

    def render(self, context: dict) -> "Component":
        """Return the card's Dash component.

        Parameters
        ----------
        context : dict
            Per-render context (e.g. user, locale, page filters). Cockpit
            currently passes an empty dict; reserved for future use.

        Returns
        -------
        Component
            Any Dash component. The cockpit wraps the result in an error
            boundary, so raising here renders an error placeholder rather
            than breaking the page.
        """
        ...
