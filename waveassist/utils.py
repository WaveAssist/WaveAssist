import requests
import json
from datetime import datetime
from typing import Type, TypeVar
from pydantic import BaseModel
from waveassist.constants import *

T = TypeVar('T', bound=BaseModel)

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



def get_email_template_credits_limit_reached(
    assistant_name: str,
    required_credits: float,
    credits_remaining: float
) -> str:
    return f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; margin: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .content {{ background-color: #fff; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
                .notice {{ border: 1px solid #ddd; color: #333; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .dashboard-button {{ display: inline-block; background-color: #428d4f; color: white !important; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 15px 0; }}
                .dashboard-button:hover {{ background-color: #2d5a2d; color: white !important; }}
                .dashboard-button:visited {{ color: white !important; }}
                .dashboard-button:link {{ color: white !important; }}
                a.dashboard-button {{ color: white !important; }}
                a.dashboard-button:visited {{ color: white !important; }}
                a.dashboard-button:link {{ color: white !important; }}
                a.dashboard-button:hover {{ color: white !important; }}
                .footer {{ font-size: 12px; color: #888; margin-top: 30px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{assistant_name}: Credit Limit Reached</h1>
                    <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                </div>
                <div class="content">
                    <div class="notice">
                        <h3>Operation Unavailable - Credit Limit Reached</h3>
                        <p>We were unable to proceed with your requested operation because your API credits have been fully utilized.</p>
                        <p><strong>Credit Details:</strong></p>
                        <ul>
                            <li>Credits Required: {required_credits}</li>
                            <li>Credits Remaining: {credits_remaining}</li>
                        </ul>
                        <p><strong>To continue using {assistant_name}:</strong></p>
                        <ul>
                            <li>Check your current credit balance</li>
                            <li>Purchase additional credits if needed</li>
                            <li>Review your usage patterns</li>
                        </ul>
                        <a href="{DASHBOARD_URL}" class="dashboard-button">View Dashboard & Check Credits</a>
                    </div>
                    <p><strong>Need help?</strong></p>
                    <ul>
                        <li>Contact support for credit-related questions</li>
                        <li>Review your subscription plan</li>
                        <li>Check our pricing page for credit packages</li>
                    </ul>
                </div>
                <div class="footer">
                    © {datetime.now().year} {assistant_name} | Powered by WaveAssist.
                </div>
            </div>
        </body>
        </html>
        """


def extract_json_from_content(content: str) -> str:
    """
    Extract JSON content from a string, handling markdown code blocks.
    
    Args:
        content: Raw content that may contain JSON wrapped in markdown code blocks
        
    Returns:
        Extracted JSON string
    """
    content = content.strip()
    # Try to extract JSON if it's wrapped in markdown code blocks
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return content


def parse_json_response(
    content: str,
    response_model: Type[T],
    model: str
) -> T:
    """
    Parse JSON content and validate it against a Pydantic model.
    
    Args:
        content: JSON string to parse (may contain markdown code blocks)
        response_model: Pydantic model class to validate against
        model: Model name (for error messages)
        
    Returns:
        Validated instance of response_model
        
    Raises:
        ValueError: If JSON parsing or validation fails
    """
    try:
        # Extract JSON from markdown if needed
        json_content = extract_json_from_content(content)
        # Parse JSON
        parsed_data = json.loads(json_content)
        # Validate with Pydantic
        return response_model(**parsed_data)
    except json.JSONDecodeError as e:
        content_preview = content[:200] if content else "No content received"
        raise ValueError(
            f"Failed to parse JSON response from model '{model}'. "
            f"The model may not support structured outputs. "
            f"Error: {e}\nResponse content: {content_preview}"
        )
    except Exception as e:
        raise ValueError(
            f"Failed to validate response from model '{model}' against {response_model.__name__}. "
            f"Error: {e}"
        )


def create_json_prompt(prompt: str, response_model: Type[BaseModel]) -> str:
    """
    Create a prompt that requests JSON output matching a Pydantic schema.
    
    Args:
        prompt: Original user prompt
        response_model: Pydantic model class to generate schema from
        
    Returns:
        Enhanced prompt with JSON schema instructions
    """
    schema = response_model.model_json_schema()
    return f"""{prompt}

Please respond with a valid JSON object matching exactly this schema:
{json.dumps(schema, indent=2)}

Return ONLY the JSON object, no other text, return JSON now: """