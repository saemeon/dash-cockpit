"""URL-based sharing for configurator working lists.

This module is the *wire format* for sharing a configurator's working list
via the browser URL. It is deliberately storage-agnostic: it knows how to
encode/decode a working list to/from a base64 token and how to dispatch a
URL search string to either an inline-encoded bundle or a named preset
loader callable.

Two URL parameters are recognised on a :class:`ConfiguratorPage`:

- ``?b=<urlsafe-base64-json>`` — an inline ad-hoc working list.
- ``?preset=<group>/<name>`` — a deep-link to a preset in the configured
  :class:`~dash_cockpit._presets.PresetStore`. The bare form ``?preset=<name>``
  is shorthand for ``group=""``.

If both are present, ``?b`` wins — an inline payload is more specific than
a name reference.

The bundle wire shape is identical to ``WORKING_LIST_STORE_ID.data`` and
to :attr:`Preset.entries`: ``list[{"template_id": str, "params": dict}]``.
No new dataclass.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable
from typing import Any, TypedDict
from urllib.parse import parse_qs


class BundleEntry(TypedDict):
    """One configurator working-list entry — the unit a bundle holds.

    Matches both ``WORKING_LIST_STORE_ID.data`` items and
    :attr:`Preset.entries` items so a bundle can be loaded directly into
    either without conversion.
    """

    template_id: str
    params: dict[str, Any]


Bundle = list[BundleEntry]
"""Ordered configurator working list — the bundle wire shape."""


PresetLoader = Callable[[str, str], Bundle | None]
"""Callable that resolves a ``(group, name)`` to a bundle.

Returns ``None`` when the preset is missing or not visible to the caller.
The cockpit builds an adapter around :class:`PresetStore` at the URL-hydrator
registration site; this module never touches the store directly.
"""


def encode_bundle(working: list[dict]) -> str:
    """Encode a working list into a URL-safe base64 token.

    JSON serialisation uses ``sort_keys=True`` so the same working list
    always produces the same token — useful for share-link equality and
    cache keys.

    Parameters
    ----------
    working : list[dict]
        Working list as it lives in ``WORKING_LIST_STORE_ID.data``.

    Returns
    -------
    str
        URL-safe base64 token, padding stripped. Decode with
        :func:`decode_bundle`.

    Examples
    --------
    >>> token = encode_bundle([{"template_id": "kpi", "params": {"x": 1}}])
    >>> decode_bundle(token)
    [{'template_id': 'kpi', 'params': {'x': 1}}]
    """
    payload = json.dumps(working, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_bundle(token: str) -> Bundle | None:
    """Decode a URL token produced by :func:`encode_bundle`.

    Tolerant of missing base64 padding (re-pads automatically). Returns
    ``None`` on any parse, decode, or shape-validation error — never raises.

    Parameters
    ----------
    token : str
        URL-safe base64 token.

    Returns
    -------
    Bundle or None
        The decoded working list, or ``None`` if the token is malformed,
        not valid JSON, or has the wrong shape.
    """
    if not token:
        return None
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _validate_bundle(data)


def _validate_bundle(raw: Any) -> Bundle | None:
    """Shape-check a decoded payload. Return ``None`` on any structural fault.

    A bundle is a list of dicts; each entry must carry a string
    ``template_id`` and a dict ``params``. Anything else is rejected — we
    do not coerce, repair, or partially accept malformed payloads.
    """
    if not isinstance(raw, list):
        return None
    out: Bundle = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None
        template_id = entry.get("template_id")
        params = entry.get("params")
        if not isinstance(template_id, str) or not isinstance(params, dict):
            return None
        out.append({"template_id": template_id, "params": params})
    return out


def _split_preset_value(raw: str) -> tuple[str, str]:
    """Split a ``?preset=`` value into ``(group, name)``.

    Splits on the **first** ``/`` only — names containing further ``/``
    characters are preserved literally in the ``name`` part.

    Bare values without a ``/`` are interpreted as ``(group="", name=raw)``
    so ``?preset=foo`` continues to work in single-bucket deployments.

    Examples
    --------
    >>> _split_preset_value("foo")
    ('', 'foo')
    >>> _split_preset_value("team:finance/q3")
    ('team:finance', 'q3')
    >>> _split_preset_value("a/b/c")
    ('a', 'b/c')
    """
    group, sep, name = raw.partition("/")
    if not sep:
        return ("", group)
    return (group, name)


def resolve_from_search(
    search: str,
    preset_loader: PresetLoader | None,
) -> Bundle | None:
    """Dispatch a URL search string to either an inline bundle or a preset.

    Resolution order:

    1. If ``?b=<token>`` is present and decodes successfully, return that
       bundle. The preset loader is **not** consulted.
    2. Otherwise, if ``?preset=<value>`` is present and ``preset_loader``
       was supplied, split the value on the first ``/`` into
       ``(group, name)`` and call ``preset_loader``. Return its result.
    3. Otherwise return ``None``.

    Loader exceptions (``KeyError`` from a missing preset, ``PermissionError``
    from a non-visible group) are swallowed and become ``None``. This keeps
    the URL hydrator silent for both "not found" and "not visible to you" —
    leaking presence-vs-permission would be an information-disclosure surface.

    Parameters
    ----------
    search : str
        The browser's ``location.search`` (e.g. ``"?b=abc"``). Leading
        ``"?"`` is optional.
    preset_loader : PresetLoader or None
        Adapter callable resolving ``(group, name)`` to a bundle. When
        ``None``, the ``?preset`` branch is skipped.

    Returns
    -------
    Bundle or None
        The decoded bundle, or ``None`` when nothing usable was found.
    """
    if not search:
        return None
    params = parse_qs(search.lstrip("?"), keep_blank_values=False)

    if "b" in params and params["b"]:
        bundle = decode_bundle(params["b"][0])
        if bundle is not None:
            return bundle
        # Fall through: malformed ?b is a no-op, not an error.

    if preset_loader is not None and "preset" in params and params["preset"]:
        group, name = _split_preset_value(params["preset"][0])
        if not name:
            return None
        try:
            return preset_loader(group, name)
        except (KeyError, PermissionError):
            return None

    return None
