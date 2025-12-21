"""
Test to verify if all models support JSON response format.
Tests call_llm with response_format={"type": "json_object"}.
"""
import sys
import os
import argparse

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List
from pydantic import BaseModel
from waveassist import init, call_llm
from waveassist import _config
from waveassist.constants import OPENROUTER_API_STORED_DATA_KEY

# Mock fetch_data to return API key directly
original_fetch_data = None

def mock_fetch_data(key: str):
    """Mock fetch_data to return API key when requested."""
    if key == OPENROUTER_API_STORED_DATA_KEY:
        return mock_fetch_data.api_key
    return None

# Patch fetch_data
import waveassist
original_fetch_data = waveassist.fetch_data
waveassist.fetch_data = mock_fetch_data

# Pydantic models for response structure
class User(BaseModel):
    name: str
    age: int

class UserListResponse(BaseModel):
    users: List[User]

# Flat, non-repeated list of unique models
models_list = [
    'deepseek/deepseek-chat-v3.1',
    'anthropic/claude-sonnet-4.5',
    'x-ai/grok-4.1-fast',
    'perplexity/sonar',
    'google/gemini-3-flash-preview'
]

PROMPT = "Format the users into name and age. Users: John, 25 years old and Jane, 30 years old"

def get_api_key(api_key_param: str = None) -> str:
    """Get OpenRouter API key from parameter, environment, or skip if headless."""
    if api_key_param and api_key_param != "<here>":
        return api_key_param
    
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
    if api_key:
        return api_key
    
    import sys
    if not sys.stdin.isatty():
        return None
    
    api_key = input("Enter OpenRouter API key (or press Enter to skip): ").strip()
    return api_key if api_key else None

def test_llm_call(model_name: str) -> dict:
    """Test if a model supports JSON response format using call_llm."""
    try:
        result = call_llm(
            model=model_name,
            prompt=PROMPT,
            response_model=UserListResponse,
            max_tokens=200
        )
        
        has_two_users = len(result.users) == 2
        all_valid = all(
            isinstance(u.name, str) and isinstance(u.age, int) 
            for u in result.users
        )
        
        return {
            "model": model_name,
            "status": "success",
            "supports_json_format": True,
            "has_two_users": has_two_users,
            "all_valid": all_valid,
            "response": {"users": [{"name": u.name, "age": u.age} for u in result.users]},
            "error": None
        }
    except Exception as e:
        return {
            "model": model_name,
            "status": "error",
            "supports_json_format": False,
            "has_two_users": False,
            "all_valid": False,
            "response": None,
            "error": str(e)
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test JSON format support for all models")
    parser.add_argument("--api-key", type=str, default=None, help="OpenRouter API key")
    args = parser.parse_args()
    
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("⚠️  Skipping tests: OpenRouter API key not provided")
        print("   Set OPENROUTER_API_KEY env var or pass --api-key parameter\n")
        exit(0)
    
    # Set API key in mock
    mock_fetch_data.api_key = api_key
    
    # Initialize with dummy credentials
    _config.LOGIN_TOKEN = "test-token"
    _config.PROJECT_KEY = "test-project"
    init("test-token", "test-project")
    
    results = []
    for model_name in models_list:
        print(f"Testing {model_name}...")
        result = test_llm_call(model_name)
        results.append(result)
        
        if result["status"] == "success":
            print(f"  ✅ Success")
            print(f"  Has two users: {result['has_two_users']}")
            print(f"  All valid: {result['all_valid']}")
            print(f"  Response: {result['response']}")
        else:
            print(f"  ❌ Failed: {result['error']}")
        print()
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    success_count = sum(
        1 for r in results 
        if r["status"] == "success" and r["has_two_users"] and r["all_valid"]
    )
    print(f"Success: {success_count}/{len(results)}")
    
    import json
    print("\nResults:")
    print(json.dumps(results, indent=2))

