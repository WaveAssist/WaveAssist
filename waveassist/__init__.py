import requests
import pandas as pd
from waveassist.utils import call_post_api, call_get_api, call_post_api_with_files
from waveassist import _config
import json
import os
from dotenv import load_dotenv


from pathlib import Path

def _conditionally_load_env():
    # Only load .env if UID/project_key aren't set
    if not os.getenv("uid") or not os.getenv("project_key"):
        env_path = Path.cwd() / ".env"  # Use the project root (not library path)
        load_dotenv(dotenv_path=env_path, override=False)


def init(token: str = None, project_key: str = None, environment_key: str = None) -> None:
    _conditionally_load_env()  # Load from .env if it exists

    # Resolve UID/token
    resolved_token = (
        token or
        os.getenv("uid") or
        getattr(_config, "DEFAULT_LOGIN_TOKEN", None)
    )

    # Resolve project_key
    resolved_project_key = (
        project_key or
        os.getenv("project_key") or
        getattr(_config, "DEFAULT_PROJECT_KEY", None)
    )

    # Resolve env_key
    resolved_env_key = (
        environment_key or
        os.getenv("environment_key") or
        getattr(_config, "DEFAULT_ENVIRONMENT_KEY", None) or
        f"{resolved_project_key}_default" if resolved_project_key else None
    )

    # Validate critical keys
    if not resolved_token:
        raise ValueError("WaveAssist init failed: UID is missing. Pass explicitly or set uid in .env.")
    if not resolved_project_key:
        raise ValueError("WaveAssist init failed: project key is missing. Pass explicitly or set project_key in .env.")

    # Set config
    _config.LOGIN_TOKEN = resolved_token
    _config.PROJECT_KEY = resolved_project_key
    _config.ENVIRONMENT_KEY = resolved_env_key

def set_worker_defaults(
    token: str = None,
    project_key: str = None,
    environment_key: str = None
) -> None:
    """Set default values for login token, project key, and environment key."""
    _config.DEFAULT_LOGIN_TOKEN = token
    _config.DEFAULT_PROJECT_KEY = project_key
    _config.DEFAULT_ENVIRONMENT_KEY = environment_key

def set_default_environment_key(key: str) -> None:
    _config.DEFAULT_ENVIRONMENT_KEY = key

def store_data(key: str, data):
    """Serialize the data based on its type and store it in the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception("WaveAssist is not initialized. Please call waveassist.init(...) first.")

    if isinstance(data, pd.DataFrame):
        format = "dataframe"
        serialized_data = json.loads(data.to_json(orient="records", date_format="iso"))
    elif isinstance(data, (dict, list)):
        format = "json"
        serialized_data = data
    else:
        format = "string"
        serialized_data = str(data)

    payload = {
        'uid': _config.LOGIN_TOKEN,
        'data_type': format,
        'data': serialized_data,
        'project_key': _config.PROJECT_KEY,
        'data_key': str(key),
        'environment_key': _config.ENVIRONMENT_KEY
    }

    path = 'data/set_data_for_key/'
    success, response = call_post_api(path, payload)

    if not success:
        print("❌ Error storing data:", response)

    return success

def fetch_data(key: str):
    """Retrieve the data stored under `key` from the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception("WaveAssist is not initialized. Please call waveassist.init(...) first.")

    params = {
        'uid': _config.LOGIN_TOKEN,
        'project_key': _config.PROJECT_KEY,
        'data_key': str(key),
        'environment_key': _config.ENVIRONMENT_KEY
    }

    path = 'data/fetch_data_for_key/'
    success, response = call_get_api(path, params)

    if not success:
        print("❌ Error fetching data:", response)
        return None

    # Extract stored format and already-deserialized data
    data_type = response.get("data_type")
    data = response.get("data")

    if data_type == "dataframe":
        return pd.DataFrame(data)
    elif data_type in ["json"]:
        return data
    elif data_type == "string":
        return str(data)
    else:
        print(f"⚠️ Unsupported data_type: {data_type}")
        return None


def send_email(subject: str, html_content: str, attachment_file=None):
    """Send an email with optional attachment file object via the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception("WaveAssist is not initialized. Please call waveassist.init(...) first.")

    data = {
        'uid': _config.LOGIN_TOKEN,
        'project_key': _config.PROJECT_KEY,
        'subject': subject,
        'html_content': html_content,
    }

    files = None
    if attachment_file:
        try:
            file_name = getattr(attachment_file, 'name', 'attachment')
            files = {'attachment': (file_name, attachment_file)}
        except Exception as e:
            print("❌ Invalid attachment:", e)
            return False

    path = 'sdk/send_email/'
    success, response = call_post_api_with_files(path, data, files=files)

    if not success:
        print("❌ Error sending email:", response)
    else:
        print("✅ Email sent successfully.")

    return success
