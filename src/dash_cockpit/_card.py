"""Card protocol — the atomic unit of insight a team publishes to the cockpit.

Note: this module deliberately does not use ``from __future__ import annotations``
because :class:`TypedDict` needs ``NotRequired`` to evaluate at class-creation
time so that ``__required_keys__`` is correct.
"""

from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from dash.development.base_component import Component


class RenderContext(TypedDict):
    """Per-render context passed to every :meth:`Card.render` call.

    A frozen contract. Adding fields is forward-compatible; removing or
    renaming fields breaks every team that has read them. All fields are
    ``NotRequired`` so the cockpit can omit any it cannot supply (e.g.
    ``user`` before auth is wired); cards must treat every key as optional
    and supply their own defaults.

    Parameters
    ----------
    user : dict, optional
        Authenticated user. Populated by auth middleware when configured;
        absent in unauthenticated deployments. Shape is auth-backend-defined
        but should at minimum contain ``"id"`` and ``"email"`` when present.
        Cards filtering on identity must handle the missing case.
    locale : str, optional
        BCP-47 language tag (e.g. ``"en"``, ``"de-CH"``). Drives number
        and date formatting in cards. Defaults to ``"en"`` when absent.
    page_filters : dict, optional
        Page-scoped filter state (e.g. ``{"date_range": [...], "division": "EMEA"}``).
        Set by the page, not the card. Cards must not write here. Currently
        always absent — reserved for a future filter-bar feature.
    request_id : str, optional
        Opaque correlation id for tracing one user request across logs and
        downstream service calls. Cards should propagate it on outbound HTTP.

    Notes
    -----
    Cards must read defensively::

        def render(context: RenderContext):
            user = context.get("user") or {}
            locale = context.get("locale", "en")

    Reading ``context["user"]`` directly will raise ``KeyError`` in
    deployments without auth.
    """

    user: NotRequired[dict]
    locale: NotRequired[str]
    page_filters: NotRequired[dict]
    request_id: NotRequired[str]


class RenderContext(TypedDict):
    """Per-render context passed to every :meth:`Card.render` call.

    A frozen contract. Adding fields is forward-compatible; removing or
    renaming fields breaks every team that has read them. All fields are
    ``NotRequired`` so the cockpit can omit any it cannot supply (e.g.
    ``user`` before auth is wired); cards must treat every key as optional
    and supply their own defaults.

    Parameters
    ----------
    user : dict, optional
        Authenticated user. Populated by auth middleware when configured;
        absent in unauthenticated deployments. Shape is auth-backend-defined
        but should at minimum contain ``"id"`` and ``"email"`` when present.
        Cards filtering on identity must handle the missing case.
    locale : str, optional
        BCP-47 language tag (e.g. ``"en"``, ``"de-CH"``). Drives number
        and date formatting in cards. Defaults to ``"en"`` when absent.
    page_filters : dict, optional
        Page-scoped filter state (e.g. ``{"date_range": [...], "division": "EMEA"}``).
        Set by the page, not the card. Cards must not write here. Currently
        always absent — reserved for a future filter-bar feature.
    request_id : str, optional
        Opaque correlation id for tracing one user request across logs and
        downstream service calls. Cards should propagate it on outbound HTTP.

    Notes
    -----
    Cards must read defensively::

        def render(context: RenderContext):
            user = context.get("user") or {}
            locale = context.get("locale", "en")

    Reading ``context["user"]`` directly will raise ``KeyError`` in
    deployments without auth.
    """

    user: NotRequired[dict]
    locale: NotRequired[str]
    page_filters: NotRequired[dict]
    request_id: NotRequired[str]


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

    def render(self, context: "RenderContext") -> "Component | dict":
        """Return the card's Dash component, or a slot dict.

        Two return shapes are supported:

        - **Bare ``Component``** — shorthand for ``{"body": Component}``. The
          historical shape; existing cards keep working unchanged.
        - **Slot dict** — ``{"body": Component, "settings": Component, "actions": dict}``.
          ``body`` is required; ``settings`` and ``actions`` are optional.
          See :func:`unwrap_render_result`.

        Parameters
        ----------
        context : RenderContext
            Per-render context. See :class:`RenderContext` for the field
            contract. All fields are optional; read defensively with
            ``context.get("locale", "en")``.

        Returns
        -------
        Component or dict
            The card's body, optionally with ``settings`` (drawer panel) and
            ``actions`` (``⋮`` menu items overriding ``CARD_META["actions"]``).
        """
        ...


def unwrap_render_result(
    result: "Component | dict",
) -> tuple["Component", "Component | None", "dict | None"]:
    """Split a ``render`` return value into ``(body, settings, actions)``.

    Cards may return either a bare component (legacy shape) or a slot dict.
    This helper hides the branching so call sites in :mod:`_layout`,
    :mod:`_configurator`, and :mod:`_refresh` can always treat the three
    surfaces uniformly.

    Parameters
    ----------
    result : Component or dict
        Whatever ``card.render(context)`` returned. Bare components are
        treated as ``{"body": result}``. Dict results must contain a
        ``"body"`` key; ``"settings"`` and ``"actions"`` are optional.

    Returns
    -------
    body : Component
        The card body — placed in the grid cell by the cockpit.
    settings : Component or None
        Optional settings panel — opened in the side drawer when the user
        clicks ``⋮`` → "Settings". ``None`` when the card has no settings.
    actions : dict or None
        Optional render-time override for ``CARD_META["actions"]``. ``None``
        means "use the static default from CARD_META". An empty dict means
        "no actions" (different from None).

    Raises
    ------
    ValueError
        If ``result`` is a dict missing the required ``"body"`` key.
    """
    if isinstance(result, dict):
        if "body" not in result:
            raise ValueError(
                "Card.render returned a dict without a 'body' key; "
                "include 'body': <Component> or return the Component directly."
            )
        return (
            result["body"],
            result.get("settings"),
            result.get("actions"),
        )
    return (result, None, None)
