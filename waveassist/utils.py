import requests
import json
import re
from datetime import datetime
from typing import Type, TypeVar, get_origin, get_args, Any, Union
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


def _get_type_name(annotation: Any) -> str:
    """Get a clean type name from a type annotation."""
    if annotation is None:
        return "null"
    
    origin = get_origin(annotation)
    
    # Handle Optional types (Union[X, None])
    if origin is Union:
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _get_type_name(non_none_args[0])
        return " | ".join(_get_type_name(a) for a in non_none_args)
    
    # Handle List, Dict, etc.
    if origin is list:
        args = get_args(annotation)
        if args:
            return f"list[{_get_type_name(args[0])}]"
        return "list"
    
    if origin is dict:
        args = get_args(annotation)
        if args and len(args) == 2:
            return f"dict[{_get_type_name(args[0])}, {_get_type_name(args[1])}]"
        return "dict"
    
    # Handle Pydantic BaseModel (nested models)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__
    
    # Handle basic types
    if hasattr(annotation, '__name__'):
        return annotation.__name__
    
    return str(annotation)


def _generate_template_value(field_annotation: Any, field_description: str | None) -> Any:
    """Generate a template value for a field, handling nested models."""
    # Check if it's a Pydantic model (nested)
    origin = get_origin(field_annotation)
    
    # Handle Optional types
    if origin is Union:
        args = get_args(field_annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if non_none_args:
            return _generate_template_value(non_none_args[0], field_description)
    
    # Handle List of Pydantic models
    if origin is list:
        args = get_args(field_annotation)
        if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
            return [generate_json_template_dict(args[0])]
        elif args:
            return [f"<{_get_type_name(args[0])}>"]
        return ["<item>"]
    
    # Handle nested Pydantic model
    if isinstance(field_annotation, type) and issubclass(field_annotation, BaseModel):
        return generate_json_template_dict(field_annotation)
    
    # Use description if available, otherwise type name
    if field_description:
        return field_description
    return f"<{_get_type_name(field_annotation)}>"


def generate_json_template_dict(model: Type[BaseModel]) -> dict:
    """Generate a template dictionary showing the structure and descriptions."""
    template = {}
    for name, field in model.model_fields.items():
        template[name] = _generate_template_value(field.annotation, field.description)
    return template


def generate_json_template(model: Type[BaseModel]) -> str:
    """Generate a clean JSON string showing the structure and descriptions."""
    return json.dumps(generate_json_template_dict(model), indent=2)


def _find_balanced_json(content: str, start_char: str, end_char: str) -> str | None:
    """
    Find a balanced JSON object or array starting from the first occurrence of start_char.
    
    Args:
        content: Content to search in
        start_char: Opening character ('{' or '[')
        end_char: Closing character ('}' or ']')
        
    Returns:
        The matched JSON string, or None if not found
    """
    start_idx = content.find(start_char)
    if start_idx == -1:
        return None
    
    depth = 0
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(content)):
        char = content[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    # Found matching closing brace/bracket
                    return content[start_idx:i + 1]
    
    return None


def extract_json_from_content(content: str) -> Union[dict, list]:
    """
    Extract and parse JSON from content using multiple strategies.
    
    Args:
        content: Raw content that may contain JSON
        
    Returns:
        Parsed JSON as a dictionary or list
        
    Raises:
        ValueError: If no valid JSON could be extracted
    """
    if not content:
        raise ValueError("Empty content received")
    
    content = content.strip()
    
    # Strategy 1: Try parsing directly (content is pure JSON)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract from ```json code blocks
    json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Extract from generic ``` code blocks
    code_block_match = re.search(r'```\s*([\s\S]*?)\s*```', content)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Find JSON object pattern { ... } with balanced matching
    json_object_str = _find_balanced_json(content, '{', '}')
    if json_object_str:
        try:
            return json.loads(json_object_str)
        except json.JSONDecodeError:
            pass
    
    # Strategy 5: Find JSON array pattern [ ... ] with balanced matching
    json_array_str = _find_balanced_json(content, '[', ']')
    if json_array_str:
        try:
            return json.loads(json_array_str)
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Could not extract valid JSON from content: {content[:200]}...")


def soft_parse(model_class: Type[T], raw_data: dict) -> T:
    """
    Parse data into a Pydantic model leniently.
    
    - Ignores extra fields not in the model
    - Allows missing optional fields (they become None)
    - Attempts type coercion where possible
    - Falls back to model_construct if validation fails (e.g., missing required fields)
    - Fills in missing fields with None or their default values
    
    This ensures LLM responses are never wasted - we return whatever data was gathered.
    
    Args:
        model_class: Pydantic model class to parse into
        raw_data: Raw dictionary data from LLM
        
    Returns:
        Instance of the model class (may have None for missing required fields)
    """
    # Filter to only valid keys
    valid_keys = set(model_class.model_fields.keys())
    filtered_data = {k: v for k, v in raw_data.items() if k in valid_keys}
    
    # 1. Try normal validation first (handles type coercion, defaults, etc.)
    try:
        return model_class.model_validate(filtered_data)
    except Exception:
        pass
    
    # 2. Safety Fallback: "Just give me what you found"
    # model_construct bypasses validation - returns whatever data is available
    obj = model_class.model_construct(**filtered_data)
    
    # 3. Fill in the gaps: Ensure every field exists
    from pydantic_core import PydanticUndefined
    for field_name in valid_keys:
        if not hasattr(obj, field_name):
            # Set to the field's default if it has one, otherwise None
            field_info = model_class.model_fields[field_name]
            default_value = field_info.default
            
            # Check for default_factory if default is undefined
            if default_value is PydanticUndefined:
                # Check if there's a default_factory to call
                default_factory = getattr(field_info, 'default_factory', None)
                if default_factory is not None and callable(default_factory):
                    default_value = default_factory()
                else:
                    default_value = None
            
            setattr(obj, field_name, default_value)
    
    return obj


def parse_json_response(content: str, response_model: Type[T], model: str) -> T:
    """
    Parse JSON content and validate it against a Pydantic model with soft parsing.
    
    Args:
        content: JSON string to parse (may contain markdown code blocks)
        response_model: Pydantic model class to validate against
        model: Model name (for error messages)
        
    Returns:
        Validated instance of response_model
        
    Raises:
        ValueError: If JSON extraction or parsing fails
    """
    try:
        # Extract JSON using multiple strategies
        parsed_data = extract_json_from_content(content)

        # If the extracted JSON is an array, take the first element
        # (since the model expects an object/dict)
        if isinstance(parsed_data, list):
            if len(parsed_data) == 0:
                raise ValueError(
                    f"Expected JSON object but got empty array. "
                    f"The model '{response_model.__name__}' requires an object, not an array."
                )
            parsed_data = parsed_data[0]
            # Ensure it's a dict after extracting from array
            if not isinstance(parsed_data, dict):
                raise ValueError(
                    f"Expected JSON object but got array with non-object element. "
                    f"The model '{response_model.__name__}' requires an object."
                )

        # Soft parse with lenient validation
        return soft_parse(response_model, parsed_data)
        
    except ValueError as e:
        # Re-raise ValueError from extract_json_from_content
        raise ValueError(f"Failed to parse response from model '{model}': {e}")
    except Exception as e:
        raise ValueError(
            f"Failed to validate response from model '{model}' against {response_model.__name__}. "
            f"Error: {e}"
        )


def create_json_prompt(prompt: str, response_model: Type[BaseModel]) -> str:
    """
    Create a prompt that requests JSON output matching a Pydantic model structure.
    
    Args:
        prompt: Original user prompt
        response_model: Pydantic model class to generate template from
        
    Returns:
        Enhanced prompt with JSON structure instructions
    """
    template = generate_json_template(response_model)
    return f"""{prompt}
    
    Respond with a JSON object following this structure:
    {template}
    
    Return ONLY the JSON object, no explanations or other text. Return JSON now:"""