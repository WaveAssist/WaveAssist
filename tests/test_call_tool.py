"""Tests for waveassist.call_tool and waveassist.is_test_run."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import waveassist
from waveassist import init, call_tool, is_test_run, _config


# ------------------ mock state ------------------

mock_db = {}                 # data store (reset between tests)
post_calls = []              # records every POST for assertions
execute_response = None      # set per-test to control /tools/execute reply
execute_fail_first = False   # flip to trigger one transient failure before success


def _mock_post(path, payload):
    post_calls.append((path, payload))

    if path == "data/set_data_for_key/":
        mock_db[payload["data_key"]] = {
            "data": payload["data"],
            "data_type": payload["data_type"],
        }
        return True, {"message": "ok"}

    if path == "api/v1/tools/execute":
        global execute_fail_first
        if execute_fail_first:
            execute_fail_first = False
            return False, "simulated transient error"
        return True, execute_response

    return False, {"error": "Invalid POST path"}


def _mock_get(path, params):
    if path == "data/fetch_data_for_key/":
        key = params["data_key"]
        if key in mock_db:
            return True, {
                "data": mock_db[key]["data"],
                "data_type": mock_db[key]["data_type"],
            }
        return False, {"error": "Key not found"}
    return False, {"error": "Invalid GET path"}


waveassist.call_post_api = _mock_post
waveassist.call_get_api = _mock_get


def reset():
    _config.LOGIN_TOKEN = None
    _config.PROJECT_KEY = None
    _config.ENVIRONMENT_KEY = None
    _config.RUN_ID = None
    mock_db.clear()
    post_calls.clear()
    global execute_response, execute_fail_first
    execute_response = None
    execute_fail_first = False
    for k in ("uid", "project_key", "environment_key"):
        os.environ.pop(k, None)


def _init():
    init("tok-test", "proj-test")


# ------------------ is_test_run ------------------

def test_is_test_run_default_false():
    reset(); _init()
    assert is_test_run() is False
    print("✅ test_is_test_run_default_false")


def test_is_test_run_true_when_set():
    reset(); _init()
    mock_db["_is_test_run"] = {"data": True, "data_type": "json"}
    assert is_test_run() is True
    print("✅ test_is_test_run_true_when_set")


# ------------------ call_tool happy paths ------------------

def test_call_tool_read_returns_result():
    reset(); _init()
    global execute_response
    execute_response = {
        "success": "1",
        "status": "200",
        "message": "OK",
        "data": {
            "test_preview": False,
            "action_slug": "GMAIL_FETCH_EMAILS",
            "result": {"data": {"messages": [{"subject": "hi"}]}, "successful": True},
        },
    }
    out = call_tool("GMAIL_FETCH_EMAILS", {"max_results": 5})
    assert out["test_preview"] is False
    assert out["result"]["data"]["messages"][0]["subject"] == "hi"
    # execute payload looks right
    exec_payload = [p for path, p in post_calls if path == "api/v1/tools/execute"][0]
    assert exec_payload["uid"] == "tok-test"
    assert exec_payload["project_key"] == "proj-test"
    assert exec_payload["action_slug"] == "GMAIL_FETCH_EMAILS"
    assert exec_payload["is_test_run"] == "false"
    print("✅ test_call_tool_read_returns_result")


def test_call_tool_write_real_run_returns_result():
    reset(); _init()
    global execute_response
    execute_response = {
        "success": "1",
        "status": "200",
        "message": "OK",
        "data": {
            "test_preview": False,
            "action_slug": "GMAIL_SEND_EMAIL",
            "result": {"successful": True, "data": {"id": "abc123"}},
        },
    }
    out = call_tool("GMAIL_SEND_EMAIL", {"recipient_email": "x@y.com", "body": "hi"})
    assert out["test_preview"] is False
    assert out["result"]["successful"] is True
    # no preview key stored
    assert not any(k.startswith("test_preview_") for k in mock_db.keys())
    print("✅ test_call_tool_write_real_run_returns_result")


# ------------------ call_tool gated write ------------------

def test_call_tool_write_test_run_stores_preview():
    reset(); _init()
    mock_db["_is_test_run"] = {"data": True, "data_type": "json"}

    args = {"recipient_email": "x@y.com", "body": "hi", "subject": "s"}
    global execute_response
    execute_response = {
        "success": "1",
        "status": "200",
        "message": "OK (test preview)",
        "data": {
            "test_preview": True,
            "action_slug": "GMAIL_SEND_EMAIL",
            "toolkit_slug": "gmail",
            "arguments": args,
            "note": "Write skipped because is_test_run=true.",
        },
    }
    out = call_tool("GMAIL_SEND_EMAIL", args)
    assert out["test_preview"] is True
    assert out["key"].startswith("test_preview_GMAIL_SEND_EMAIL_")
    assert out["arguments"] == args

    # preview record actually stored in our mock backend
    stored = mock_db[out["key"]]["data"]
    assert stored["action_slug"] == "GMAIL_SEND_EMAIL"
    assert stored["toolkit_slug"] == "gmail"
    assert stored["arguments"] == args

    # execute POST was sent with is_test_run=true
    exec_payload = [p for path, p in post_calls if path == "api/v1/tools/execute"][0]
    assert exec_payload["is_test_run"] == "true"
    print("✅ test_call_tool_write_test_run_stores_preview")


# ------------------ call_tool errors ------------------

def test_call_tool_error_envelope_raises():
    reset(); _init()
    global execute_response
    execute_response = {
        "success": "0",
        "status": "404",
        "message": "Action not found: FAKE_ACTION",
    }
    try:
        call_tool("FAKE_ACTION", {})
    except RuntimeError as e:
        assert "Action not found: FAKE_ACTION" in str(e)
        print("✅ test_call_tool_error_envelope_raises")
        return
    raise AssertionError("expected RuntimeError")


def test_call_tool_transient_failure_retries():
    reset(); _init()
    global execute_response, execute_fail_first
    execute_fail_first = True
    execute_response = {
        "success": "1",
        "status": "200",
        "message": "OK",
        "data": {"test_preview": False, "result": {"ok": True}},
    }
    out = call_tool("SOME_ACTION", {})
    assert out["result"]["ok"] is True
    # exactly 2 execute attempts
    exec_attempts = [c for c in post_calls if c[0] == "api/v1/tools/execute"]
    assert len(exec_attempts) == 2
    print("✅ test_call_tool_transient_failure_retries")


def test_call_tool_not_initialized_raises():
    reset()
    try:
        call_tool("X", {})
    except RuntimeError as e:
        assert "not initialized" in str(e)
        print("✅ test_call_tool_not_initialized_raises")
        return
    raise AssertionError("expected RuntimeError")


def test_call_tool_bad_args():
    reset(); _init()
    try:
        call_tool("", {})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty slug")

    try:
        call_tool("X", "not a dict")  # type: ignore[arg-type]
    except ValueError:
        print("✅ test_call_tool_bad_args")
        return
    raise AssertionError("expected ValueError for non-dict args")


# ------------------ runner ------------------

if __name__ == "__main__":
    test_is_test_run_default_false()
    test_is_test_run_true_when_set()
    test_call_tool_read_returns_result()
    test_call_tool_write_real_run_returns_result()
    test_call_tool_write_test_run_stores_preview()
    test_call_tool_error_envelope_raises()
    test_call_tool_transient_failure_retries()
    test_call_tool_not_initialized_raises()
    test_call_tool_bad_args()
    print("\nAll tests passed.")
