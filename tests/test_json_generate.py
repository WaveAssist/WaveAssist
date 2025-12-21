"""
Tests for JSON template generation functions: generate_json_template_dict, 
generate_json_template, and create_json_prompt.
"""

import sys
import os
import json

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from waveassist.utils import (
    create_json_prompt,
    generate_json_template,
    generate_json_template_dict,
)


# ==================== TEST MODELS ====================

class SimpleModel(BaseModel):
    """Simple model with basic types."""
    name: str
    age: int
    score: float
    is_active: bool


class ModelWithDescriptions(BaseModel):
    """Model with field descriptions."""
    title: str = Field(description="The title of the item")
    count: int = Field(description="Number of items")
    price: float = Field(description="Price in USD")


class ModelWithOptionals(BaseModel):
    """Model with optional fields."""
    required_field: str
    optional_string: Optional[str] = None
    optional_int: Optional[int] = None
    optional_with_default: str = "default_value"


class ModelWithLists(BaseModel):
    """Model with list fields."""
    tags: List[str]
    scores: List[int]
    items: List[float]


class Address(BaseModel):
    """Nested model for address."""
    street: str
    city: str
    zip_code: str = Field(description="Postal code")


class Person(BaseModel):
    """Model with nested Pydantic model."""
    name: str
    email: str
    address: Address


class OrderItem(BaseModel):
    """Item in an order."""
    product_name: str
    quantity: int
    unit_price: float


class Order(BaseModel):
    """Model with list of nested models."""
    order_id: str
    customer_name: str
    items: List[OrderItem]
    total: float


class DeeplyNested(BaseModel):
    """Deeply nested structure."""
    level1_field: str
    nested: Person  # Person contains Address


class ComplexModel(BaseModel):
    """Complex model with various field types."""
    id: str = Field(description="Unique identifier")
    name: str
    tags: List[str] = Field(description="List of tags")
    metadata: Optional[Dict[str, str]] = None
    owner: Optional[Person] = None
    items: List[OrderItem] = Field(description="Order items")


# ==================== TESTS FOR generate_json_template_dict ====================

def test_simple_model_template():
    """Test template generation for simple model with basic types."""
    result = generate_json_template_dict(SimpleModel)
    
    assert "name" in result
    assert "age" in result
    assert "score" in result
    assert "is_active" in result
    
    # Check type placeholders
    assert result["name"] == "<str>"
    assert result["age"] == "<int>"
    assert result["score"] == "<float>"
    assert result["is_active"] == "<bool>"
    
    print("✅ test_simple_model_template passed")


def test_model_with_descriptions():
    """Test that descriptions are used instead of type placeholders."""
    result = generate_json_template_dict(ModelWithDescriptions)
    
    assert result["title"] == "The title of the item"
    assert result["count"] == "Number of items"
    assert result["price"] == "Price in USD"
    
    print("✅ test_model_with_descriptions passed")


def test_model_with_optionals():
    """Test template generation for optional fields."""
    result = generate_json_template_dict(ModelWithOptionals)
    
    assert "required_field" in result
    assert "optional_string" in result
    assert "optional_int" in result
    assert "optional_with_default" in result
    
    # Optional fields should show the inner type
    assert result["optional_string"] == "<str>"
    assert result["optional_int"] == "<int>"
    
    print("✅ test_model_with_optionals passed")


def test_model_with_lists():
    """Test template generation for list fields."""
    result = generate_json_template_dict(ModelWithLists)
    
    assert result["tags"] == ["<str>"]
    assert result["scores"] == ["<int>"]
    assert result["items"] == ["<float>"]
    
    print("✅ test_model_with_lists passed")


def test_nested_model():
    """Test template generation for nested Pydantic models."""
    result = generate_json_template_dict(Person)
    
    assert result["name"] == "<str>"
    assert result["email"] == "<str>"
    
    # Address should be expanded as a nested dict
    assert isinstance(result["address"], dict)
    assert result["address"]["street"] == "<str>"
    assert result["address"]["city"] == "<str>"
    assert result["address"]["zip_code"] == "Postal code"  # Uses description
    
    print("✅ test_nested_model passed")


def test_list_of_nested_models():
    """Test template generation for list of nested Pydantic models."""
    result = generate_json_template_dict(Order)
    
    assert result["order_id"] == "<str>"
    assert result["customer_name"] == "<str>"
    assert result["total"] == "<float>"
    
    # items should be a list with one expanded nested model
    assert isinstance(result["items"], list)
    assert len(result["items"]) == 1
    assert isinstance(result["items"][0], dict)
    assert result["items"][0]["product_name"] == "<str>"
    assert result["items"][0]["quantity"] == "<int>"
    assert result["items"][0]["unit_price"] == "<float>"
    
    print("✅ test_list_of_nested_models passed")


def test_deeply_nested_model():
    """Test template generation for deeply nested structures."""
    result = generate_json_template_dict(DeeplyNested)
    
    assert result["level1_field"] == "<str>"
    assert isinstance(result["nested"], dict)
    assert result["nested"]["name"] == "<str>"
    assert isinstance(result["nested"]["address"], dict)
    assert result["nested"]["address"]["city"] == "<str>"
    
    print("✅ test_deeply_nested_model passed")


def test_complex_model():
    """Test template generation for complex model with various types."""
    result = generate_json_template_dict(ComplexModel)
    
    assert result["id"] == "Unique identifier"  # Uses description
    assert result["name"] == "<str>"
    # List types show structure, not description (more informative)
    assert result["tags"] == ["<str>"]  # Shows list structure
    assert result["metadata"] == "<dict[str, str]>"
    
    # Optional nested model should be expanded
    assert isinstance(result["owner"], dict)
    assert result["owner"]["name"] == "<str>"
    
    # List of nested models shows structure (expanded nested model)
    assert isinstance(result["items"], list)
    assert len(result["items"]) == 1
    assert isinstance(result["items"][0], dict)
    assert result["items"][0]["product_name"] == "<str>"
    
    print("✅ test_complex_model passed")


# ==================== TESTS FOR generate_json_template (string output) ====================

def test_generate_json_template_is_valid_json():
    """Test that generate_json_template produces valid JSON."""
    result = generate_json_template(SimpleModel)
    
    # Should be valid JSON
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert "name" in parsed
    
    print("✅ test_generate_json_template_is_valid_json passed")


def test_generate_json_template_nested():
    """Test that nested models produce valid JSON."""
    result = generate_json_template(Person)
    
    parsed = json.loads(result)
    assert isinstance(parsed["address"], dict)
    assert "street" in parsed["address"]
    
    print("✅ test_generate_json_template_nested passed")


# ==================== TESTS FOR create_json_prompt ====================

def test_create_json_prompt_contains_original_prompt():
    """Test that create_json_prompt includes the original prompt."""
    original_prompt = "Extract user information from: John Doe, age 30"
    result = create_json_prompt(original_prompt, SimpleModel)
    
    assert original_prompt in result
    print("✅ test_create_json_prompt_contains_original_prompt passed")


def test_create_json_prompt_contains_structure():
    """Test that create_json_prompt includes the JSON structure."""
    result = create_json_prompt("Test prompt", SimpleModel)
    
    assert "name" in result
    assert "age" in result
    assert "<str>" in result or "<int>" in result
    
    print("✅ test_create_json_prompt_contains_structure passed")


def test_create_json_prompt_contains_instructions():
    """Test that create_json_prompt includes JSON instructions."""
    result = create_json_prompt("Test prompt", SimpleModel)
    
    assert "JSON" in result
    assert "Return ONLY" in result or "only" in result.lower()
    
    print("✅ test_create_json_prompt_contains_instructions passed")


def test_create_json_prompt_with_nested_model():
    """Test create_json_prompt with nested model shows full structure."""
    result = create_json_prompt("Extract order info", Order)
    
    # Should contain nested structure
    assert "order_id" in result
    assert "items" in result
    assert "product_name" in result
    
    print("✅ test_create_json_prompt_with_nested_model passed")


# ==================== RUN ALL TESTS ====================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing generate_json_template_dict")
    print("="*60)
    test_simple_model_template()
    test_model_with_descriptions()
    test_model_with_optionals()
    test_model_with_lists()
    test_nested_model()
    test_list_of_nested_models()
    test_deeply_nested_model()
    test_complex_model()
    
    print("\n" + "="*60)
    print("Testing generate_json_template")
    print("="*60)
    test_generate_json_template_is_valid_json()
    test_generate_json_template_nested()
    
    print("\n" + "="*60)
    print("Testing create_json_prompt")
    print("="*60)
    test_create_json_prompt_contains_original_prompt()
    test_create_json_prompt_contains_structure()
    test_create_json_prompt_contains_instructions()
    test_create_json_prompt_with_nested_model()
    
    print("\n" + "="*60)
    print("🎉 All JSON generation tests passed!")
    print("="*60)

