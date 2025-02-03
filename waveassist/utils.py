import requests

BASE_URL ="https://api.waveassist.io"
def call_api(path, body):
    url = f"{BASE_URL}/{path}"
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    try:
        response = requests.post(url, data=body, headers=headers)
        response_dict = response.json()
        if response_dict.get("success") == "1":
            if "data" in response_dict:
                return response_dict["data"]
            else:
                raise ValueError("Invalid response structure")
        else:
            error_message = response_dict.get("message", "Unknown error")
            raise ValueError(error_message)
    except Exception as e:
        print(f"Error: {e}")
        raise
