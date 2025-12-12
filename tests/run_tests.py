import sys
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from waveassist import init, store_data, fetch_data, set_worker_defaults
from waveassist import _config

# Dummy in-memory store
mock_db = {}

# ------------------ MOCKING ------------------

def mock_call_post_api(path, payload):
    if path == 'data/set_data_for_key/':
        key = payload['data_key']
        mock_db[key] = {
            "data": payload["data"],
            "data_type": payload["data_type"]
        }
        return True, {"message": "ok"}
    return False, {"error": "Invalid POST path"}

def mock_call_get_api(path, params):
    if path == 'data/fetch_data_for_key/':
        key = params['data_key']
        if key in mock_db:
            return True, {
                "data": mock_db[key]["data"],
                "data_type": mock_db[key]["data_type"]
            }
        return False, {"error": "Key not found"}
    return False, {"error": "Invalid GET path"}

# Patch into waveassist module
import waveassist
waveassist.call_post_api = mock_call_post_api
waveassist.call_get_api = mock_call_get_api

# ------------------ RESET FUNCTION ------------------

def reset_state():
    _config.LOGIN_TOKEN = None
    _config.PROJECT_KEY = None
    _config.ENVIRONMENT_KEY = None
    _config.DEFAULT_ENVIRONMENT_KEY = None
    _config.DEFAULT_PROJECT_KEY = None
    _config.DEFAULT_LOGIN_TOKEN = None
    mock_db.clear()
    for var in ["uid", "project_key", "environment_key"]:
        os.environ.pop(var, None)

# ------------------ TEST CASES ------------------

def test_store_and_fetch_string():
    reset_state()
    init("test-token", "my-project")
    store_data("greeting", "Hello, WaveAssist!")
    result = fetch_data("greeting")
    assert result == "Hello, WaveAssist!"
    print("✅ test_store_and_fetch_string passed")

def test_store_and_fetch_json():
    reset_state()
    init("test-token", "my-project")
    data = {"name": "Alice", "score": 95}
    store_data("user_profile", data)
    result = fetch_data("user_profile")
    assert result == data
    print("✅ test_store_and_fetch_json passed")

def test_store_and_fetch_dataframe():
    reset_state()
    init("test-token", "my-project")
    df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 88]})
    store_data("user_scores", df)
    result = fetch_data("user_scores")
    pd.testing.assert_frame_equal(result, df)
    print("✅ test_store_and_fetch_dataframe passed")

def test_fetch_without_init_raises():
    reset_state()
    try:
        fetch_data("some_key")
        assert False, "Expected an exception when init was not called"
    except Exception as e:
        assert "not initialized" in str(e).lower()
        print("✅ test_fetch_without_init_raises passed")

def test_default_environment_key_used():
    reset_state()
    set_worker_defaults(environment_key="fallback_env_123")
    init("test-token", "my-project")  # No env key passed
    assert _config.ENVIRONMENT_KEY == "fallback_env_123"
    print("✅ test_default_environment_key_used passed")

def test_env_fallbacks():
    reset_state()
    set_worker_defaults(token="fallback-token", project_key="fallback-project", environment_key="fallback-env")
    init()  # Use fallback resolution
    assert _config.LOGIN_TOKEN == "fallback-token"
    assert _config.PROJECT_KEY == "fallback-project"
    assert _config.ENVIRONMENT_KEY == "fallback-env"
    print("✅ test_env_fallbacks passed")

def test_init_from_dotenv():
    reset_state()

    # Create a temporary .env file with final format
    env_path = Path(".env")
    env_path.write_text("""\
uid='xxxxxxxx-492b-4294-8154-xxxxxxxx'
project_key='gitzoid_test'
environment_key='default_gitzoid_test'
""")

    # Load .env explicitly
    load_dotenv(dotenv_path=env_path, override=True)

    # Should use .env values
    init()

    assert _config.LOGIN_TOKEN == "xxxxxxxx-492b-4294-8154-xxxxxxxx"
    assert _config.PROJECT_KEY == "gitzoid_test"
    assert _config.ENVIRONMENT_KEY == "default_gitzoid_test"
    print("✅ test_init_from_dotenv passed")

    # Clean up
    env_path.unlink(missing_ok=True)

# ------------------ RUN ALL ------------------

if __name__ == "__main__":
    test_store_and_fetch_string()
    test_store_and_fetch_json()
    test_store_and_fetch_dataframe()
    test_fetch_without_init_raises()
    test_default_environment_key_used()
    test_env_fallbacks()
    test_init_from_dotenv()
    print("\n🎉 All tests passed.")
