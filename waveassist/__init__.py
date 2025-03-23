import requests
import pandas as pd
from waveassist.utils import call_api
from waveassist import _config
import json

def init(token: str, project_key: str, environment_key: str = None) -> None:
    """Initialize WaveAssist with credentials and project context."""
    _config.LOGIN_TOKEN = token
    _config.PROJECT_KEY = project_key
    _config.ENVIRONMENT_KEY = environment_key or f"{project_key}_default"


def store_data(key: str, data):
    """Serialize the data based on its type and store it in the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception("WaveAssist is not initialized. Please call waveassist.init(...) first.")

    if isinstance(data, pd.DataFrame):
        format = "dataframe"
        serialized_data = data.to_json(orient="records")
    elif isinstance(data, (dict, list)):
        format = "json"
        serialized_data = json.dumps(data)
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
    success, response = call_api(path, payload)

    if not success:
        print("❌ Error storing data:", response)

    return success

def fetch_data(key: str):
    """Retrieve the data stored under `key` from the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception("WaveAssist is not initialized. Please call waveassist.init(...) first.")

    payload = {
        'uid': _config.LOGIN_TOKEN,
        'project_key': _config.PROJECT_KEY,
        'data_key': str(key),
        'environment_key': _config.ENVIRONMENT_KEY
    }

    path = 'data/fetch_data_for_key/'
    success, response = call_api(path, payload)

    if not success:
        print("❌ Error fetching data:", response)
        return None

    # Extract stored format and serialized data
    data_type = response.get("data_type")
    serialized_data = response.get("data")

    if data_type == "dataframe":
        return pd.read_json(serialized_data, orient="records")
    elif data_type == "json":
        return json.loads(serialized_data)
    elif data_type == "string":
        return serialized_data
    else:
        print(f"⚠️ Unsupported data_type: {data_type}")
        return None
