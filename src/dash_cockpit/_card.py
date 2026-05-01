from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from dash.development.base_component import Component


class CardMeta(TypedDict):
    id: str
    title: str
    team: str
    description: str
    refresh_interval: int  # seconds; 0 = no auto-refresh
    category: str
    # Widget size in grid units, (width, height). Default (1, 1).
    # Page declares total grid_columns (e.g. 4); a card with size=(2, 1) spans
    # half a 4-column page. Height units stack vertically per row.
    size: NotRequired[tuple[int, int]]
    # Optional per-card actions exposed to the cockpit menu. Each action is a
    # small mapping with at least `id` and `label`. The cockpit renders these
    # as menu items and emits pattern-matching callback events when clicked.
    actions: NotRequired[list[dict]]


@runtime_checkable
class Card(Protocol):
    CARD_META: CardMeta

    def render(self, context: dict) -> "Component": ...
