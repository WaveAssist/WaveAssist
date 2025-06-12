import requests

BASE_URL ="https://api.waveassist.io"
def call_post_api(path, body) -> tuple:
    url = f"{BASE_URL}/{path}"
    headers = { "Content-Type": "application/json" }  # JSON content
    try:
        response = requests.post(url, json=body, headers=headers)  # Sends proper JSON
        response_dict = response.json()

        if str(response_dict.get("success")) == "1":
            return True, response_dict
        else:
            error_message = response_dict.get("message", "Unknown error")
            return False, error_message
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False, str(e)

def call_post_api_with_files(path, body, files=None) -> tuple:
    url = f"{BASE_URL}/{path}"
    try:
        response = requests.post(url, data=body, files=files or {})
        response_dict = response.json()
        if str(response_dict.get("success")) == "1":
            return True, response_dict
        else:
            error_message = response_dict.get("message", "Unknown error")
            return False, error_message
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False, str(e)



def call_get_api(path, params) -> tuple:
    url = f"{BASE_URL}/{path}"
    headers = { "Content-Type": "application/json" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response_dict = response.json()

        if str(response_dict.get("success")) == "1":
            return True, response_dict.get("data", {})
        else:
            error_message = response_dict.get("message", "Unknown error")
            return False, error_message

    except Exception as e:
        print(f"❌ API GET call failed: {e}")
        return False, str(e)
