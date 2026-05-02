import base64

import pytest

from dash_cockpit._share import (
    _split_preset_value,
    decode_bundle,
    encode_bundle,
    resolve_from_search,
)


def _b64(payload: bytes | str) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


# --- encode/decode round-trip -------------------------------------------------


def test_round_trip_empty():
    assert decode_bundle(encode_bundle([])) == []


def test_round_trip_single_entry():
    bundle = [{"template_id": "kpi", "params": {"region": "CH"}}]
    assert decode_bundle(encode_bundle(bundle)) == bundle


def test_round_trip_multiple_entries():
    bundle = [
        {"template_id": "a", "params": {"x": 1}},
        {"template_id": "b", "params": {"y": [1, 2, 3], "nested": {"k": "v"}}},
        {"template_id": "c", "params": {}},
    ]
    assert decode_bundle(encode_bundle(bundle)) == bundle


def test_encode_is_deterministic():
    bundle = [{"template_id": "x", "params": {"b": 2, "a": 1}}]
    assert encode_bundle(bundle) == encode_bundle(bundle)
    bundle_reordered = [{"params": {"a": 1, "b": 2}, "template_id": "x"}]
    assert encode_bundle(bundle) == encode_bundle(bundle_reordered)


def test_encode_strips_padding():
    token = encode_bundle([{"template_id": "x", "params": {}}])
    assert "=" not in token


def test_encode_uses_urlsafe_alphabet():
    bundle = [{"template_id": "x" * 100, "params": {"v": "?" * 100}}]
    token = encode_bundle(bundle)
    assert "+" not in token
    assert "/" not in token


# --- decode error handling ----------------------------------------------------


def test_decode_empty_string_returns_none():
    assert decode_bundle("") is None


def test_decode_invalid_base64_returns_none():
    assert decode_bundle("!!!not-base64!!!") is None


def test_decode_non_json_returns_none():
    assert decode_bundle(_b64("not json at all")) is None


def test_decode_non_list_returns_none():
    assert decode_bundle(_b64('{"not": "a list"}')) is None


def test_decode_missing_params_returns_none():
    assert decode_bundle(_b64('[{"template_id": "x"}]')) is None


def test_decode_missing_template_id_returns_none():
    assert decode_bundle(_b64('[{"params": {}}]')) is None


def test_decode_non_string_template_id_returns_none():
    assert decode_bundle(_b64('[{"template_id": 42, "params": {}}]')) is None


def test_decode_non_dict_params_returns_none():
    assert decode_bundle(_b64('[{"template_id": "x", "params": "not-a-dict"}]')) is None


def test_decode_non_dict_entry_returns_none():
    assert decode_bundle(_b64('["not-a-dict"]')) is None


def test_decode_invalid_utf8_returns_none():
    raw = b"\xff\xfe\xfd"
    token = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    assert decode_bundle(token) is None


# --- _split_preset_value ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("foo", ("", "foo")),
        ("team:finance/q3", ("team:finance", "q3")),
        ("a/b/c", ("a", "b/c")),
        ("/q3", ("", "q3")),
        ("user:alice/", ("user:alice", "")),
        ("", ("", "")),
    ],
)
def test_split_preset_value(raw, expected):
    assert _split_preset_value(raw) == expected


# --- resolve_from_search ------------------------------------------------------


def _bundle():
    return [{"template_id": "k", "params": {"a": 1}}]


def test_resolve_empty_search_returns_none():
    assert resolve_from_search("", lambda g, n: _bundle()) is None


def test_resolve_b_returns_inline_bundle():
    token = encode_bundle(_bundle())
    called = []

    def loader(g, n):
        called.append((g, n))
        return None

    result = resolve_from_search(f"?b={token}", loader)
    assert result == _bundle()
    assert called == []


def test_resolve_preset_bare_name_calls_loader_with_empty_group():
    seen = []

    def loader(g, n):
        seen.append((g, n))
        return _bundle()

    assert resolve_from_search("?preset=foo", loader) == _bundle()
    assert seen == [("", "foo")]


def test_resolve_preset_with_group():
    seen = []

    def loader(g, n):
        seen.append((g, n))
        return _bundle()

    assert resolve_from_search("?preset=team:finance/q3", loader) == _bundle()
    assert seen == [("team:finance", "q3")]


def test_resolve_preset_with_extra_slashes():
    seen = []

    def loader(g, n):
        seen.append((g, n))
        return _bundle()

    assert resolve_from_search("?preset=a/b/c", loader) == _bundle()
    assert seen == [("a", "b/c")]


def test_resolve_b_wins_when_both_present():
    token = encode_bundle(_bundle())
    other_bundle = [{"template_id": "other", "params": {}}]
    called = []

    def loader(g, n):
        called.append((g, n))
        return other_bundle

    result = resolve_from_search(f"?b={token}&preset=foo", loader)
    assert result == _bundle()
    assert called == []


def test_resolve_malformed_b_falls_through_to_preset():
    """Graceful degradation: a broken inline token does not block ?preset."""

    def loader(g, n):
        return _bundle()

    result = resolve_from_search("?b=!!!garbage!!!&preset=foo", loader)
    assert result == _bundle()


def test_resolve_missing_preset_returns_none():
    assert resolve_from_search("?preset=missing", lambda g, n: None) is None


def test_resolve_preset_keyerror_returns_none():
    def loader(g, n):
        raise KeyError(f"{g!r}/{n!r}")

    assert resolve_from_search("?preset=foo", loader) is None


def test_resolve_preset_permissionerror_returns_none():
    def loader(g, n):
        raise PermissionError("not visible")

    assert resolve_from_search("?preset=user:bob/secret", loader) is None


def test_resolve_preset_other_exception_propagates():
    """Only KeyError and PermissionError are swallowed; other bugs surface."""

    def loader(g, n):
        raise ValueError("bug in loader")

    with pytest.raises(ValueError):
        resolve_from_search("?preset=foo", loader)


def test_resolve_preset_with_no_loader_returns_none():
    assert resolve_from_search("?preset=foo", None) is None


def test_resolve_preset_with_empty_name_returns_none():
    """?preset=group/ has empty name — refuse rather than load 'group / ' """
    called = []

    def loader(g, n):
        called.append((g, n))
        return _bundle()

    assert resolve_from_search("?preset=user:alice/", loader) is None
    assert called == []


def test_resolve_b_takes_first_value_when_repeated():
    token1 = encode_bundle([{"template_id": "first", "params": {}}])
    token2 = encode_bundle([{"template_id": "second", "params": {}}])
    result = resolve_from_search(f"?b={token1}&b={token2}", None)
    assert result == [{"template_id": "first", "params": {}}]


def test_resolve_search_without_leading_question_mark():
    token = encode_bundle(_bundle())
    assert resolve_from_search(f"b={token}", None) == _bundle()
