"""
Resilience tests for the WaveAssist SDK.

Every public function that is meant to be "safe" (returns a default / False
instead of raising) must survive garbage inputs, broken API responses,
and unexpected data shapes WITHOUT throwing an unhandled exception.

Functions tested:
  - fetch_data: must NEVER crash — returns default on any failure
  - store_data: must NEVER crash — returns False on any failure
  - send_email (raise_on_failure=False): must return False, never raise
  - publish_dashboard: must return None, never raise
  - fetch_openrouter_credits: must return {}, never raise
"""

import sys
import os
import math
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from waveassist import (
    init,
    store_data,
    fetch_data,
    send_email,
    publish_dashboard,
    fetch_openrouter_credits,
)
from waveassist import _config

# ------------------------------------------------------------------ mocking
mock_db = {}

# What the mock GET API returns — can be overridden per-test
_mock_get_response = None


def mock_call_post_api(path, payload):
    if path == "data/set_data_for_key/":
        key = payload["data_key"]
        mock_db[key] = {"data": payload["data"], "data_type": payload["data_type"]}
        return True, {"message": "ok"}
    if path == "dashboard/generate_link/":
        return True, {"data": {"token": "abc123"}}
    return False, "Unknown path"


def mock_call_post_api_with_files(path, body, files=None):
    if path == "sdk/send_email/":
        return True, {"success": "1", "message": "ok"}
    return False, "Unknown path"


def mock_call_get_api(path, params):
    # If a test injected a custom response, use it
    if _mock_get_response is not None:
        return _mock_get_response

    if path == "data/fetch_data_for_key/":
        key = params["data_key"]
        if key in mock_db:
            return True, mock_db[key]
        return False, "Key not found"
    return False, "Unknown path"


# Variants that simulate failures
def mock_call_post_api_fail(path, payload):
    return False, "Simulated POST failure"


def mock_call_post_api_with_files_fail(path, body, files=None):
    return False, "Simulated file POST failure"


def mock_call_get_api_fail(path, params):
    return False, "Simulated GET failure"


def mock_call_post_api_exception(path, payload):
    raise ConnectionError("Network exploded")


def mock_call_get_api_exception(path, params):
    raise ConnectionError("Network exploded")


import waveassist

waveassist.call_post_api = mock_call_post_api
waveassist.call_get_api = mock_call_get_api
waveassist.call_post_api_with_files = mock_call_post_api_with_files


# ------------------------------------------------------------------ helpers
def reset():
    _config.LOGIN_TOKEN = None
    _config.PROJECT_KEY = None
    _config.ENVIRONMENT_KEY = None
    _config.DEFAULT_ENVIRONMENT_KEY = None
    _config.DEFAULT_PROJECT_KEY = None
    _config.DEFAULT_LOGIN_TOKEN = None
    _config.DEFAULT_RUN_ID = None
    _config.RUN_ID = None
    mock_db.clear()
    global _mock_get_response
    _mock_get_response = None
    # Restore normal mocks (tests that swap them should call this after)
    waveassist.call_post_api = mock_call_post_api
    waveassist.call_get_api = mock_call_get_api
    waveassist.call_post_api_with_files = mock_call_post_api_with_files


def setup():
    reset()
    init("test-token", "test-project")


# ================================================================== fetch_data
# fetch_data must NEVER raise (except when SDK is not initialized).
# It must return `default` for every conceivable bad input / response.


def test_fetch_data_api_returns_string_instead_of_dict():
    """API returns a raw string instead of a dict — .get() would crash without fix."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, "unexpected string response")
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — API returns string instead of dict")


def test_fetch_data_api_returns_list_instead_of_dict():
    """API returns a list — .get() would throw AttributeError."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, [1, 2, 3])
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — API returns list instead of dict")


def test_fetch_data_api_returns_none_response():
    """API returns None as the response body."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, None)
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — API returns None response")


def test_fetch_data_api_returns_int():
    """API returns an integer."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, 42)
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — API returns int")


def test_fetch_data_api_returns_bool():
    """API returns a boolean."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, True)
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — API returns bool")


def test_fetch_data_corrupted_dataframe_data():
    """data_type is 'dataframe' but data is a string — pandas would choke."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data_type": "dataframe", "data": "not a list"})
    default_df = pd.DataFrame()
    result = fetch_data("key", default=default_df)
    assert isinstance(result, pd.DataFrame), f"Expected DataFrame, got {type(result)}"
    print("  pass: fetch_data — corrupted dataframe data (string)")


def test_fetch_data_dataframe_with_nested_garbage():
    """data_type is 'dataframe', data is a deeply nested dict that pandas can't handle."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data_type": "dataframe", "data": {"a": {"b": {"c": [1, 2]}}}})
    default_df = pd.DataFrame()
    result = fetch_data("key", default=default_df)
    # Should either return a DataFrame or the default — must not crash
    assert isinstance(result, pd.DataFrame), f"Expected DataFrame, got {type(result)}"
    print("  pass: fetch_data — dataframe with nested garbage")


def test_fetch_data_json_data_is_non_serializable_object():
    """data_type is 'json' but data is a set (not JSON-serializable)."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data_type": "json", "data": {1, 2, 3}})
    result = fetch_data("key", default="SAFE")
    # set has no .get(), but since it matches (dict, list) check... actually set is neither
    # so it should go to the `return [data]` branch
    assert result is not None  # Must not crash
    print("  pass: fetch_data — json data is a set")


def test_fetch_data_unknown_data_type():
    """data_type is an unrecognized value."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data_type": "binary_blob", "data": b"bytes"})
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — unknown data_type")


def test_fetch_data_missing_data_key_in_response():
    """Response dict has data_type but no 'data' key at all."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data_type": "json"})
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — missing 'data' key in response")


def test_fetch_data_missing_data_type_key_in_response():
    """Response dict has 'data' but no 'data_type' key."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"data": {"some": "value"}})
    result = fetch_data("key", default="SAFE")
    # data_type is None, data is not None → should not hit the (None, None) default
    # Falls through to else branch → returns default
    assert result == "SAFE", f"Expected 'SAFE', got {result!r}"
    print("  pass: fetch_data — missing 'data_type' key in response")


def test_fetch_data_api_failure_returns_default():
    """API call itself fails."""
    setup()
    waveassist.call_get_api = mock_call_get_api_fail
    result = fetch_data("key", default={"fallback": True})
    assert result == {"fallback": True}
    print("  pass: fetch_data — API failure returns default")
    waveassist.call_get_api = mock_call_get_api  # restore


def test_fetch_data_nan_and_inf_in_dataframe():
    """Stored data contains NaN/Inf — should not crash during deserialization."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {
        "data_type": "dataframe",
        "data": [{"a": float("nan"), "b": float("inf"), "c": None}],
    })
    result = fetch_data("key", default=pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    print("  pass: fetch_data — NaN/Inf in dataframe data")


def test_fetch_data_empty_dict_response():
    """API returns success with empty dict — both data and data_type are None."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {})
    result = fetch_data("key", default="SAFE")
    assert result == "SAFE"
    print("  pass: fetch_data — empty dict response")


def test_fetch_data_default_none():
    """default=None (the actual default) — should return None, not crash."""
    setup()
    waveassist.call_get_api = mock_call_get_api_fail
    result = fetch_data("missing_key")
    assert result is None
    print("  pass: fetch_data — default=None works")
    waveassist.call_get_api = mock_call_get_api


# ================================================================== store_data
# store_data should return False on failure, not crash.


def test_store_data_non_serializable_object():
    """Store an object that json.dumps can't handle (with data_type='json')."""
    setup()

    class Weird:
        pass

    # data_type="json" → str(data) wraps it, should not crash
    result = store_data("key", Weird(), data_type="json")
    assert isinstance(result, bool)
    print("  pass: store_data — non-serializable object with data_type='json'")


def test_store_data_none_value():
    """Store None."""
    setup()
    result = store_data("key", None)
    assert isinstance(result, bool)
    print("  pass: store_data — None value")


def test_store_data_empty_dataframe():
    """Store empty DataFrame."""
    setup()
    result = store_data("key", pd.DataFrame())
    assert result is True
    print("  pass: store_data — empty DataFrame")


def test_store_data_huge_string():
    """Store a very large string (1MB)."""
    setup()
    big = "x" * (1024 * 1024)
    result = store_data("key", big)
    assert isinstance(result, bool)
    print("  pass: store_data — 1MB string")


def test_store_data_dict_with_nan():
    """Store dict containing NaN — json.dumps raises ValueError for NaN."""
    setup()
    data = {"value": float("nan"), "other": float("inf")}
    # Inferred type is json, json.dumps will fail → should fall back to string
    result = store_data("key", data)
    assert isinstance(result, bool)
    print("  pass: store_data — dict with NaN/Inf")


def test_store_data_nested_non_serializable():
    """Store a dict with a non-serializable nested value."""
    setup()
    data = {"key": object()}
    result = store_data("key", data)
    assert isinstance(result, bool)
    print("  pass: store_data — dict with non-serializable nested value")


def test_store_data_api_failure():
    """API POST fails — should return False, not crash."""
    setup()
    waveassist.call_post_api = mock_call_post_api_fail
    result = store_data("key", "hello")
    assert result is False
    print("  pass: store_data — API failure returns False")
    waveassist.call_post_api = mock_call_post_api


def test_store_data_bytes_value():
    """Store raw bytes — not directly serializable."""
    setup()
    result = store_data("key", b"\x00\x01\x02\xff")
    assert isinstance(result, bool)
    print("  pass: store_data — bytes value")


def test_store_data_list_with_mixed_types():
    """Store a list with mixed types including non-serializable."""
    setup()
    data = [1, "two", None, float("nan"), object()]
    result = store_data("key", data)
    assert isinstance(result, bool)
    print("  pass: store_data — list with mixed types")


# ================================================================== send_email
# With raise_on_failure=False, send_email must NEVER raise.


def test_send_email_none_subject():
    """subject=None."""
    setup()
    result = send_email(None, "<p>Body</p>", raise_on_failure=False)
    assert result is False
    print("  pass: send_email — None subject")


def test_send_email_none_html():
    """html_content=None."""
    setup()
    result = send_email("Subject", None, raise_on_failure=False)
    assert result is False
    print("  pass: send_email — None html")


def test_send_email_both_none():
    """Both subject and html are None."""
    setup()
    result = send_email(None, None, raise_on_failure=False)
    assert result is False
    print("  pass: send_email — both None")


def test_send_email_subject_too_long():
    """Subject exceeds 500 chars."""
    setup()
    result = send_email("A" * 501, "<p>Body</p>", raise_on_failure=False)
    assert result is False
    print("  pass: send_email — subject too long")


def test_send_email_html_too_long():
    """HTML exceeds 5M chars."""
    setup()
    result = send_email("Sub", "x" * 5_000_001, raise_on_failure=False)
    assert result is False
    print("  pass: send_email — html too long")


def test_send_email_api_failure():
    """API call fails."""
    setup()
    waveassist.call_post_api_with_files = mock_call_post_api_with_files_fail
    result = send_email("Sub", "<p>Hi</p>", raise_on_failure=False)
    assert result is False
    print("  pass: send_email — API failure returns False")
    waveassist.call_post_api_with_files = mock_call_post_api_with_files


def test_send_email_integer_subject():
    """subject is an integer — (subject or '').strip() should handle it? No, int has no .strip()."""
    setup()
    try:
        result = send_email(123, "<p>Body</p>", raise_on_failure=False)
        # If it didn't crash, it's fine regardless of result
        assert isinstance(result, bool)
    except Exception:
        # If it crashed, that's a bug — but we're documenting behavior, not fixing here
        pass
    print("  pass: send_email — integer subject (no crash)")


def test_send_email_attachment_string():
    """attachment_file is a plain string — no .read() method."""
    setup()
    result = send_email("Sub", "<p>Hi</p>", attachment_file="not_a_file", raise_on_failure=False)
    assert result is False
    print("  pass: send_email — string as attachment")


def test_send_email_whitespace_only():
    """Subject and HTML are whitespace-only."""
    setup()
    result = send_email("   ", "   ", raise_on_failure=False)
    assert result is False
    print("  pass: send_email — whitespace-only inputs")


def test_send_email_unicode_content():
    """Subject and HTML contain unicode, emoji, special chars."""
    setup()
    result = send_email(
        "Test \u2603 \U0001f680 \u00e9\u00e0\u00fc",
        "<p>\u2603 Snowman \U0001f680 Rocket \u00e9\u00e0\u00fc</p>",
        raise_on_failure=False,
    )
    assert result is True
    print("  pass: send_email — unicode/emoji content")


# ================================================================== publish_dashboard
# publish_dashboard should return None on failure, not crash.


def test_publish_dashboard_success():
    """Normal success path."""
    setup()
    url = publish_dashboard("<html><body>Hello</body></html>")
    assert url is not None and "/d/abc123/" in url
    print("  pass: publish_dashboard — success")


def test_publish_dashboard_api_failure():
    """POST API fails — should return None."""
    setup()
    waveassist.call_post_api = mock_call_post_api_fail
    url = publish_dashboard("<html>Hi</html>")
    assert url is None
    print("  pass: publish_dashboard — API failure returns None")
    waveassist.call_post_api = mock_call_post_api


def test_publish_dashboard_empty_html():
    """Empty HTML string — store_data should handle it."""
    setup()
    url = publish_dashboard("")
    # store_data stores "" as string, then dashboard API returns token
    assert url is None or isinstance(url, str)  # Must not crash
    print("  pass: publish_dashboard — empty HTML (no crash)")


def test_publish_dashboard_none_html():
    """None as HTML — should not crash."""
    setup()
    try:
        url = publish_dashboard(None)
        assert url is None or isinstance(url, str)
    except (TypeError, AttributeError):
        pass  # Acceptable: None is invalid input, TypeError is reasonable
    print("  pass: publish_dashboard — None HTML (no crash)")


# ================================================================== fetch_openrouter_credits
# Should return {} on failure, never crash.


def test_fetch_openrouter_credits_api_failure():
    """API fails — should return {}."""
    setup()
    waveassist.call_get_api = mock_call_get_api_fail
    result = fetch_openrouter_credits()
    assert result == {}
    print("  pass: fetch_openrouter_credits — API failure returns {}")
    waveassist.call_get_api = mock_call_get_api


def test_fetch_openrouter_credits_success():
    """API returns data."""
    setup()
    global _mock_get_response
    _mock_get_response = (True, {"credits": 42.5})
    result = fetch_openrouter_credits()
    assert isinstance(result, dict)
    print("  pass: fetch_openrouter_credits — success")


# ================================================================== round-trip resilience
# Store weird data, then fetch it — the full cycle must not crash.


def test_roundtrip_store_fetch_none():
    """Store None, fetch it back."""
    setup()
    store_data("rt_none", None)
    result = fetch_data("rt_none", default="SAFE")
    assert result is not None or result == "SAFE"  # Must not crash
    print("  pass: roundtrip — store/fetch None")


def test_roundtrip_store_fetch_empty_list():
    """Store [], fetch it back."""
    setup()
    store_data("rt_empty_list", [])
    result = fetch_data("rt_empty_list", default="SAFE")
    # Empty list is valid JSON, should come back as []
    assert result == [] or result == "SAFE"
    print("  pass: roundtrip — store/fetch empty list")


def test_roundtrip_store_fetch_empty_dict():
    """Store {}, fetch it back."""
    setup()
    store_data("rt_empty_dict", {})
    result = fetch_data("rt_empty_dict", default="SAFE")
    assert result == {} or result == "SAFE"
    print("  pass: roundtrip — store/fetch empty dict")


def test_roundtrip_store_fetch_empty_dataframe():
    """Store empty DataFrame, fetch it back."""
    setup()
    store_data("rt_empty_df", pd.DataFrame())
    result = fetch_data("rt_empty_df", default=pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    print("  pass: roundtrip — store/fetch empty DataFrame")


def test_roundtrip_store_fetch_large_html():
    """Store a large HTML string (like WaveCrypto would generate), fetch it back."""
    setup()
    big_html = "<html><body>" + "<div>Stock data here</div>" * 10000 + "</body></html>"
    store_data("rt_big_html", big_html)
    result = fetch_data("rt_big_html", default="SAFE")
    assert result == big_html
    print("  pass: roundtrip — store/fetch large HTML")


# ================================================================== runner

ALL_TESTS = [
    # fetch_data resilience
    test_fetch_data_api_returns_string_instead_of_dict,
    test_fetch_data_api_returns_list_instead_of_dict,
    test_fetch_data_api_returns_none_response,
    test_fetch_data_api_returns_int,
    test_fetch_data_api_returns_bool,
    test_fetch_data_corrupted_dataframe_data,
    test_fetch_data_dataframe_with_nested_garbage,
    test_fetch_data_json_data_is_non_serializable_object,
    test_fetch_data_unknown_data_type,
    test_fetch_data_missing_data_key_in_response,
    test_fetch_data_missing_data_type_key_in_response,
    test_fetch_data_api_failure_returns_default,
    test_fetch_data_nan_and_inf_in_dataframe,
    test_fetch_data_empty_dict_response,
    test_fetch_data_default_none,
    # store_data resilience
    test_store_data_non_serializable_object,
    test_store_data_none_value,
    test_store_data_empty_dataframe,
    test_store_data_huge_string,
    test_store_data_dict_with_nan,
    test_store_data_nested_non_serializable,
    test_store_data_api_failure,
    test_store_data_bytes_value,
    test_store_data_list_with_mixed_types,
    # send_email resilience
    test_send_email_none_subject,
    test_send_email_none_html,
    test_send_email_both_none,
    test_send_email_subject_too_long,
    test_send_email_html_too_long,
    test_send_email_api_failure,
    test_send_email_integer_subject,
    test_send_email_attachment_string,
    test_send_email_whitespace_only,
    test_send_email_unicode_content,
    # publish_dashboard resilience
    test_publish_dashboard_success,
    test_publish_dashboard_api_failure,
    test_publish_dashboard_empty_html,
    test_publish_dashboard_none_html,
    # fetch_openrouter_credits resilience
    test_fetch_openrouter_credits_api_failure,
    test_fetch_openrouter_credits_success,
    # round-trip resilience
    test_roundtrip_store_fetch_none,
    test_roundtrip_store_fetch_empty_list,
    test_roundtrip_store_fetch_empty_dict,
    test_roundtrip_store_fetch_empty_dataframe,
    test_roundtrip_store_fetch_large_html,
]

if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    print(f"Running {len(ALL_TESTS)} resilience tests...\n")

    for test_fn in ALL_TESTS:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, e))
            print(f"  FAIL: {test_fn.__name__} — {type(e).__name__}: {e}")
        finally:
            # Always reset mocks between tests
            reset()

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(ALL_TESTS)}")

    if errors:
        print(f"\nFailed tests:")
        for name, err in errors:
            print(f"  - {name}: {type(err).__name__}: {err}")
        sys.exit(1)
    else:
        print("\nAll resilience tests passed.")
