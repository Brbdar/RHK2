import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_ui_echo import (
    _cache_json,
    _echo_state_render_payload,
    _render_compare_table_cached,
    _render_import_table_cached,
)


def test_echo_state_render_payload_ignores_ui_autofill_metadata() -> None:
    state_a = {
        "parsed": {"lvef": 55},
        "meta": {"ok": True, "source": "browser_pdf"},
        "has_file": True,
    }
    state_b = {
        **state_a,
        "_ui_autofill_values": {"lvef": 55},
        "_ui_autofill_keys": ["lvef"],
    }

    assert _cache_json(_echo_state_render_payload(state_a)) == _cache_json(_echo_state_render_payload(state_b))


def test_echo_renderer_cache_hits_on_identical_payloads() -> None:
    payload = {"parsed": {"lvef": 55}, "meta": {"ok": True}, "has_file": True}
    payload_json = _cache_json(payload)

    _render_import_table_cached.cache_clear()
    _render_compare_table_cached.cache_clear()

    _render_import_table_cached(payload_json, "Aktuell")
    _render_import_table_cached(payload_json, "Aktuell")
    import_info = _render_import_table_cached.cache_info()
    assert import_info.hits >= 1

    _render_compare_table_cached(payload_json, payload_json)
    _render_compare_table_cached(payload_json, payload_json)
    compare_info = _render_compare_table_cached.cache_info()
    assert compare_info.hits >= 1
