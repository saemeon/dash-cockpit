"""Reserved action IDs and pattern-matching trigger helpers.

Kept separate from ``_chrome`` so modules that need only these constants
(``_refresh``, ``_app``) don't have to import the full chrome build tree.
"""

from __future__ import annotations

STD_REFRESH = "_refresh"
STD_ABOUT = "_about"
STD_SETTINGS = "_settings"
"""Reserved IDs for cockpit-supplied standard actions.

Underscore-prefixed so collisions with team-defined IDs are obvious. Don't
use these for custom actions in ``CARD_META["actions"]`` or render-time
slot dicts — the cockpit auto-injects them and registers their callbacks.
"""


def _triggered_card_id(ctx) -> str | None:
    """Extract ``card_id`` from a pattern-matching trigger, or return ``None``.

    Every per-card pattern-matching id in the cockpit (action menu items,
    refresh interval ticks, refresh button clicks) carries a ``card_id``
    field. This helper centralises the boilerplate for pulling it out of
    ``callback_context.triggered`` so the call sites can focus on what to
    do with it.

    Parameters
    ----------
    ctx : dash.callback_context
        The callback context inside a Dash callback.

    Returns
    -------
    str or None
        The triggering element's ``card_id``, or ``None`` if there's no
        trigger or the trigger isn't a pattern-matching dict id.
    """
    if not ctx.triggered:
        return None
    import json as _json

    trigger_id = ctx.triggered[0]["prop_id"].rsplit(".", 1)[0]
    try:
        parsed = _json.loads(trigger_id)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    cid = parsed.get("card_id")
    return cid if isinstance(cid, str) else None
