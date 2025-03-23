import requests

BASE_URL ="https://api.waveassist.io"
def call_api(path, body) -> tuple:
    url = f"{BASE_URL}/{path}"
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    try:
        response = requests.post(url, data=body, headers=headers)
        response_dict = response.json()
        if str(response_dict.get("success")) == "1":
            return True, response_dict
        else:
            error_message = response_dict.get("message", "Unknown error")
            return False, error_message
    except Exception as e:
        print(f"Error: {e}")
        return False, str(e)
