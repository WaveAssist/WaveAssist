import requests
import pandas as pd
from waveassist.utils import *
from waveassist import _config
import json
import os
from dotenv import load_dotenv
from typing import Type, TypeVar
from pydantic import BaseModel

from pathlib import Path
import instructor
from openai import OpenAI
from openai import APIError, NotFoundError
from datetime import datetime
from waveassist.constants import *


# TypeVar for generic type hinting: T represents any Pydantic BaseModel subclass
# This allows call_llm() to return the exact type of the response_model passed in
T = TypeVar('T', bound=BaseModel)


def _conditionally_load_env():
    # Only load .env if UID/project_key aren't set
    if not os.getenv("uid") or not os.getenv("project_key"):
        env_path = Path.cwd() / ".env"  # Use the project root (not library path)
        load_dotenv(dotenv_path=env_path, override=False)


def init(
    token: str = None,
    project_key: str = None,
    environment_key: str = None,
    run_id: str = None,
    check_credits: bool = False,
) -> None:
    _conditionally_load_env()  # Load from .env if it exists

    # Resolve UID/token
    resolved_token = (
        token or os.getenv("uid") or getattr(_config, "DEFAULT_LOGIN_TOKEN", None)
    )

    # Resolve project_key
    resolved_project_key = (
        project_key
        or os.getenv("project_key")
        or getattr(_config, "DEFAULT_PROJECT_KEY", None)
    )

    # Resolve env_key
    resolved_env_key = (
        environment_key
        or os.getenv("environment_key")
        or getattr(_config, "DEFAULT_ENVIRONMENT_KEY", None)
        or f"{resolved_project_key}_default"
        if resolved_project_key
        else None
    )

    # Resolve run_id
    resolved_run_id = (
        run_id or os.getenv("run_id") or getattr(_config, "DEFAULT_RUN_ID", None)
    )

    # Convert run_id to string if it exists
    if resolved_run_id is not None:
        resolved_run_id = str(resolved_run_id)

    # Validate critical keys
    if not resolved_token:
        raise ValueError(
            "WaveAssist init failed: UID is missing. Pass explicitly or set uid in .env."
        )
    if not resolved_project_key:
        raise ValueError(
            "WaveAssist init failed: project key is missing. Pass explicitly or set project_key in .env."
        )

    # Set config
    _config.LOGIN_TOKEN = resolved_token
    _config.PROJECT_KEY = resolved_project_key
    _config.ENVIRONMENT_KEY = resolved_env_key
    _config.RUN_ID = resolved_run_id

    # Check credits if requested
    if check_credits:
        credits_available = str(fetch_data('credits_available') or "1")
        if credits_available == "0":
            raise ValueError('Credits not available, skipping this operation')


def set_worker_defaults(
    token: str = None,
    project_key: str = None,
    environment_key: str = None,
    run_id: str = None,
) -> None:
    """Set default values for login token, project key, environment key, and run_id."""
    _config.DEFAULT_LOGIN_TOKEN = token
    _config.DEFAULT_PROJECT_KEY = project_key
    _config.DEFAULT_ENVIRONMENT_KEY = environment_key
    _config.DEFAULT_RUN_ID = run_id


def set_default_environment_key(key: str) -> None:
    _config.DEFAULT_ENVIRONMENT_KEY = key


def store_data(key: str, data, run_based: bool = False):
    """Serialize the data based on its type and store it in the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

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
        "uid": _config.LOGIN_TOKEN,
        "data_type": format,
        "data": serialized_data,
        "project_key": _config.PROJECT_KEY,
        "data_key": str(key),
        "environment_key": _config.ENVIRONMENT_KEY,
        "run_based": "1" if run_based else "0",
    }

    # Add run_id to payload if run_based is True and run_id is set
    if run_based and _config.RUN_ID:
        payload["run_id"] = str(_config.RUN_ID)

    path = "data/set_data_for_key/"
    success, response = call_post_api(path, payload)

    if not success:
        print("❌ Error storing data:", response)

    return success


def fetch_data(key: str, run_based: bool = False):
    """Retrieve the data stored under `key` from the WaveAssist backend."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    params = {
        "uid": _config.LOGIN_TOKEN,
        "project_key": _config.PROJECT_KEY,
        "data_key": str(key),
        "environment_key": _config.ENVIRONMENT_KEY,
        "run_based": "1" if run_based else "0",
    }

    # Add run_id to params if run_based is True and run_id is set
    if run_based and _config.RUN_ID:
        params["run_id"] = str(_config.RUN_ID)

    path = "data/fetch_data_for_key/"
    success, response = call_get_api(path, params)

    if not success:
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
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    data = {
        "uid": _config.LOGIN_TOKEN,
        "project_key": _config.PROJECT_KEY,
        "subject": subject,
        "html_content": html_content,
    }

    files = None
    if attachment_file:
        try:
            file_name = getattr(attachment_file, "name", "attachment")
            files = {"attachment": (file_name, attachment_file)}
        except Exception as e:
            print("❌ Invalid attachment:", e)
            return False

    path = "sdk/send_email/"
    success, response = call_post_api_with_files(path, data, files=files)

    if not success:
        print("❌ Error sending email:", response)
    else:
        print("✅ Email sent successfully.")

    return success


def fetch_openrouter_credits():
    """Fetch the credit balance for the current project."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )
    path = "/fetch_openrouter_credits/" + _config.LOGIN_TOKEN
    success, response = call_get_api(path, {})
    if not success:
        print("❌ Error fetching credit balance:", response)
        return {}
    return response


def check_credits_and_notify(
    required_credits: float,
    assistant_name: str,
) -> bool:
    """
    Check OpenRouter credits and send an email notification if insufficient credits are available.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )
    
    # Fetch current credit balance
    credits_data = fetch_openrouter_credits()
    credits_remaining = float(credits_data.get("limit_remaining", 0))
    
    # Check if sufficient credits are available
    if required_credits > credits_remaining:
        # Fetch current failure count
        failure_count = int(fetch_data("failure_count") or 0)
        
        # Only send email if we haven't sent it 3 times already
        if failure_count < 3:
            # Generate email content using template from constants
            html_content = get_email_template_credits_limit_reached(
                assistant_name=assistant_name,
                required_credits=required_credits,
                credits_remaining=credits_remaining
            )
            
            # Generate email subject
            print(f"❌ Insufficient credits. Sending notification email.")
            email_subject = f"{assistant_name} - Unavailable - Credit Limit Reached"
            send_email(subject=email_subject, html_content=html_content)
            
            # Increment and store failure count
            failure_count += 1
            store_data('failure_count', str(failure_count))
        else:
            print(f"❌ Insufficient credits. Email notification limit reached (3 emails already sent).")
        
        store_data('credits_available', "0") # Set credits_available to 0 to prevent further operations
        
        return False
    else:
        print(f"✅ Sufficient credits available. Required: {required_credits}, Remaining: {credits_remaining}")
        store_data('credits_available', "1") # Set credits_available to 1 to allow further operations
        store_data('failure_count', "0") # Reset failure count on success
        return True


def call_llm(
    model: str,
    prompt: str,
    response_model: Type[T],
    **kwargs
) -> T:
    """
    Call an LLM using Instructor library and return structured responses.
    
    Note: This function requires models that support tool use/function calling.
    If a model doesn't support tool use, it will fall back to JSON mode parsing.
    
    Args:
        model: The model name to use (e.g., "gpt-4o", "anthropic/claude-3.5-sonnet")
        prompt: The prompt to send to the LLM
        response_model: A Pydantic model class that defines the structure of the response
        **kwargs: Additional arguments to pass to the chat completion call (e.g., max_tokens, extra_body)
    Returns:
        An instance of the response_model with structured data from the LLM
    Example:
        from pydantic import BaseModel
        class UserInfo(BaseModel):
            name: str
            age: int
            email: str
        # With additional parameters
        result = waveassist.call_llm(
            model="<model_name>",
            prompt="Extract user info: John Doe, 30, john@example.com",
            response_model=UserInfo,
            max_tokens=3000,
            extra_body={"web_search_options": {"search_context_size": "medium"}})
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise Exception(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )
    
    # Fetch API key from WaveAssist data storage
    api_key = fetch_data(OPENROUTER_API_STORED_DATA_KEY)
    if not api_key:
        raise ValueError(
            "OpenRouter API key not found. Please store it using waveassist.store_data('open_router_key', 'your_api_key')"
        )
    
    # Initialize OpenAI client with OpenRouter
    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_URL
    )
    
    # Try using Instructor first (requires tool use support)
    try:
        if "perplexity" in model.lower() or "deepseek" in model.lower():
            raise Exception("This model does not support tool use, reverting to default mode.")

        patched_client = instructor.patch(client)
        response = patched_client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            **kwargs
        )
        return response
    except Exception as e:
        print(f"Running '{model}' with default mode...")
        try:
            # Create a prompt that requests JSON output
            json_prompt = create_json_prompt(prompt, response_model)
            # Call without instructor, using response_format="json_object" if supported
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": json_prompt}
                ],
                response_format={"type": "json_object"},
                **kwargs
            )
            # Parse and validate the JSON response
            content = response.choices[0].message.content
            return parse_json_response(content, response_model, model)
        except Exception as fallback_error:
            raise ValueError(
                f"Model '{model}' doesn't support tool use, "
                f"and JSON mode fallback also failed. "
                f"Original error: {e}\nFallback error: {fallback_error}"
            )
