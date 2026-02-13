import sys
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from waveassist import init, store_data, fetch_data, set_worker_defaults, send_email
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


def mock_call_post_api_with_files(path, body, files=None):
    if path == "sdk/send_email/":
        return True, {"success": "1", "message": "ok"}
    return False, "Invalid path"


# Patch into waveassist module
import waveassist
waveassist.call_post_api = mock_call_post_api
waveassist.call_get_api = mock_call_get_api
waveassist.call_post_api_with_files = mock_call_post_api_with_files

# ------------------ CREDENTIAL HELPERS ------------------

def get_test_credentials():
    """Get test credentials from environment, .env file, or use dummy values for mocked tests."""
    # Try loading .env file first
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    
    token = os.getenv("uid") or os.getenv("LOGIN_TOKEN")
    project_key = os.getenv("project_key") or os.getenv("PROJECT_KEY")
    environment_key = os.getenv("environment_key") or os.getenv("ENVIRONMENT_KEY")
    
    # If still not found, check if we're in interactive mode
    if not token or not project_key:
        import sys
        is_interactive = sys.stdin.isatty()
        
        if is_interactive:
            # Prompt for missing credentials
            if not token:
                token = input("Enter LOGIN_TOKEN (uid): ").strip()
            if not project_key:
                project_key = input("Enter PROJECT_KEY: ").strip()
        else:
            # Non-interactive: use dummy values for mocked tests
            # Since API calls are mocked, these values don't need to be real
            token = token or "test-token-dummy"
            project_key = project_key or "test-project-dummy"
    
    return token, project_key, environment_key

# ------------------ RESET FUNCTION ------------------

def reset_state():
    _config.LOGIN_TOKEN = None
    _config.PROJECT_KEY = None
    _config.ENVIRONMENT_KEY = None
    _config.DEFAULT_ENVIRONMENT_KEY = None
    _config.DEFAULT_PROJECT_KEY = None
    _config.DEFAULT_LOGIN_TOKEN = None
    _config.DEFAULT_RUN_ID = None
    mock_db.clear()
    for var in ["uid", "project_key", "environment_key", "LOGIN_TOKEN", "PROJECT_KEY", "ENVIRONMENT_KEY"]:
        os.environ.pop(var, None)

# ------------------ TEST CASES ------------------

def test_store_and_fetch_string():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    store_data("greeting", "Hello, WaveAssist!")
    result = fetch_data("greeting")
    assert result == "Hello, WaveAssist!"
    print("✅ test_store_and_fetch_string passed")

def test_store_and_fetch_json():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    data = {"name": "Alice", "score": 95}
    store_data("user_profile", data)
    result = fetch_data("user_profile")
    assert result == data
    print("✅ test_store_and_fetch_json passed")

def test_store_and_fetch_dataframe():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 88]})
    store_data("user_scores", df)
    result = fetch_data("user_scores")
    pd.testing.assert_frame_equal(result, df)
    print("✅ test_store_and_fetch_dataframe passed")


def test_store_with_explicit_data_type():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    # Store dict as string explicitly
    store_data("as_string", {"a": 1}, data_type="string")
    result = fetch_data("as_string")
    assert isinstance(result, str)
    assert "a" in result and "1" in result
    # Store string as json (wraps in {"value": "..."})
    store_data("as_json", "hello", data_type="json")
    result = fetch_data("as_json")
    assert isinstance(result, dict)
    assert result.get("value") == "hello"
    print("✅ test_store_with_explicit_data_type passed")

def test_fetch_missing_key_returns_default():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    result = fetch_data("nonexistent_key", default="my_default")
    assert result == "my_default"
    result_df = fetch_data("nonexistent_key", default=pd.DataFrame())
    assert isinstance(result_df, pd.DataFrame)
    assert result_df.empty
    print("✅ test_fetch_missing_key_returns_default passed")


def test_fetch_without_init_raises():
    reset_state()
    try:
        fetch_data("some_key")
        assert False, "Expected an exception when init was not called"
    except Exception as e:
        assert "not initialized" in str(e).lower()
        print("✅ test_fetch_without_init_raises passed")


# ------------------ SEND EMAIL TESTS ------------------

def test_send_email_success():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    ok = send_email("Test subject", "<p>Hello</p>")
    assert ok is True
    print("✅ test_send_email_success passed")


def test_send_email_empty_subject_raises_by_default():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    for bad_subject in ("", "   "):
        try:
            send_email(bad_subject, "<p>Body</p>")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Subject" in str(e) or "empty" in str(e).lower()
    # With raise_on_failure=False, returns False
    assert send_email("", "<p>Body</p>", raise_on_failure=False) is False
    print("✅ test_send_email_empty_subject_raises_by_default passed")


def test_send_email_empty_html_raises_by_default():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    for bad_html in ("", "   "):
        try:
            send_email("Subject", bad_html)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "HTML" in str(e) or "empty" in str(e).lower()
    assert send_email("Subject", "", raise_on_failure=False) is False
    print("✅ test_send_email_empty_html_raises_by_default passed")


def test_send_email_raise_on_failure_validation_raises():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    try:
        send_email("", "<p>Body</p>")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Subject" in str(e) or "empty" in str(e).lower()
    try:
        send_email("Sub", "")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "HTML" in str(e) or "empty" in str(e).lower()
    print("✅ test_send_email_raise_on_failure_validation_raises passed")


def test_send_email_without_init_raises():
    reset_state()
    try:
        send_email("Sub", "<p>Hi</p>")
        assert False, "Expected an exception when init was not called"
    except Exception as e:
        assert "not initialized" in str(e).lower()
    print("✅ test_send_email_without_init_raises passed")


def test_send_email_invalid_attachment_raises_by_default():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    try:
        send_email("Sub", "<p>Hi</p>", attachment_file=object())
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "read" in str(e).lower() or "attachment" in str(e).lower()
    assert send_email("Sub", "<p>Hi</p>", attachment_file=object(), raise_on_failure=False) is False
    print("✅ test_send_email_invalid_attachment_raises_by_default passed")


def test_send_email_valid_attachment_success():
    reset_state()
    token, project_key, _ = get_test_credentials()
    init(token, project_key)
    # File-like with .read() and .name
    class FakeFile:
        name = "report.pdf"
        def read(self):
            return b"fake pdf"
    ok = send_email("Sub", "<p>Hi</p>", attachment_file=FakeFile())
    assert ok is True
    print("✅ test_send_email_valid_attachment_success passed")


def test_default_environment_key_used():
    reset_state()
    token, project_key, _ = get_test_credentials()
    test_env_key = "test_default_env_key"
    set_worker_defaults(environment_key=test_env_key)
    init(token, project_key)  # No env key passed
    assert _config.ENVIRONMENT_KEY == test_env_key
    print("✅ test_default_environment_key_used passed")

def test_env_fallbacks():
    reset_state()
    token, project_key, env_key = get_test_credentials()
    # Use provided credentials as fallbacks
    set_worker_defaults(token=token, project_key=project_key, environment_key=env_key or f"{project_key}_default")
    init()  # Use fallback resolution
    assert _config.LOGIN_TOKEN == token
    assert _config.PROJECT_KEY == project_key
    assert _config.ENVIRONMENT_KEY is not None  # Should be set (either from fallback or auto-generated)
    print("✅ test_env_fallbacks passed")

def test_init_from_dotenv():
    reset_state()
    
    # Get credentials for the test .env file
    token, project_key, env_key = get_test_credentials()
    env_key = env_key or f"{project_key}_default"

    # Create a temporary .env file
    env_path = Path(".env")
    env_content = f"""uid='{token}'
project_key='{project_key}'
environment_key='{env_key}'
"""
    env_path.write_text(env_content)

    # Load .env explicitly
    load_dotenv(dotenv_path=env_path, override=True)

    # Should use .env values
    init()

    # Assert that values are set (not specific values)
    assert _config.LOGIN_TOKEN is not None
    assert _config.PROJECT_KEY is not None
    assert _config.ENVIRONMENT_KEY is not None
    assert _config.LOGIN_TOKEN == token
    assert _config.PROJECT_KEY == project_key
    assert _config.ENVIRONMENT_KEY == env_key
    print("✅ test_init_from_dotenv passed")

    # Clean up
    env_path.unlink(missing_ok=True)

# ------------------ RUN ALL ------------------

if __name__ == "__main__":
    # Check if we'll be using dummy credentials
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    
    token_available = bool(os.getenv("uid") or os.getenv("LOGIN_TOKEN"))
    project_key_available = bool(os.getenv("project_key") or os.getenv("PROJECT_KEY"))
    
    import sys
    is_interactive = sys.stdin.isatty()
    will_use_dummy = not (token_available and project_key_available) and not is_interactive
    
    if will_use_dummy:
        print("⚠️  Running tests with DUMMY credentials (API calls are mocked)")
        print("   Set uid/LOGIN_TOKEN and project_key/PROJECT_KEY env vars to use real credentials\n")
    else:
        print("✅ Running tests with credentials from environment/.env file\n")
    
    test_store_and_fetch_string()
    test_store_and_fetch_json()
    test_store_and_fetch_dataframe()
    test_fetch_missing_key_returns_default()
    test_store_with_explicit_data_type()
    test_fetch_without_init_raises()
    test_send_email_success()
    test_send_email_empty_subject_raises_by_default()
    test_send_email_empty_html_raises_by_default()
    test_send_email_raise_on_failure_validation_raises()
    test_send_email_without_init_raises()
    test_send_email_invalid_attachment_raises_by_default()
    test_send_email_valid_attachment_success()
    test_default_environment_key_used()
    test_env_fallbacks()
    test_init_from_dotenv()
    print("\n🎉 All tests passed.")
