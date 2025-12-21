"""
Tests for JSON extraction and parsing functions: extract_json_from_content,
soft_parse, and parse_json_response.
"""

import sys
import os

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from waveassist.utils import (
    extract_json_from_content,
    soft_parse,
    parse_json_response,
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


class ModelWithDefaultFactory(BaseModel):
    """Model with default_factory fields."""
    name: str
    items: list = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    count: int = Field(default_factory=lambda: 0)


class ModelWithMixedDefaults(BaseModel):
    """Model with mix of default and default_factory."""
    name: str
    items: list = Field(default_factory=list)
    optional_field: Optional[str] = None
    field_with_default: str = "default_value"


# ==================== TESTS FOR extract_json_from_content ====================

# Strategy 1: Pure JSON tests
def test_extract_pure_json():
    """Test extracting pure JSON content."""
    content = '{"name": "John", "age": 30}'
    result = extract_json_from_content(content)
    
    assert result["name"] == "John"
    assert result["age"] == 30
    
    print("✅ test_extract_pure_json passed")


def test_extract_pure_json_with_whitespace():
    """Test extracting pure JSON with leading/trailing whitespace."""
    content = '   {"name": "John", "age": 30}   '
    result = extract_json_from_content(content)
    
    assert result["name"] == "John"
    assert result["age"] == 30
    
    print("✅ test_extract_pure_json_with_whitespace passed")


def test_extract_pure_json_complex():
    """Test extracting complex pure JSON with nested structures."""
    content = '{"user": {"name": "John", "settings": {"theme": "dark"}}, "tags": ["a", "b"]}'
    result = extract_json_from_content(content)
    
    assert result["user"]["name"] == "John"
    assert result["user"]["settings"]["theme"] == "dark"
    assert result["tags"] == ["a", "b"]
    
    print("✅ test_extract_pure_json_complex passed")


def test_extract_pure_json_array():
    """Test extracting pure JSON array."""
    content = '[{"id": 1}, {"id": 2}]'
    result = extract_json_from_content(content)
    
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == 1
    
    print("✅ test_extract_pure_json_array passed")


# Strategy 2: ```json code blocks
def test_extract_json_from_markdown_block():
    """Test extracting JSON from markdown code block."""
    content = '''Here is the result:
```json
{"name": "Alice", "score": 95}
```
'''
    result = extract_json_from_content(content)
    
    assert result["name"] == "Alice"
    assert result["score"] == 95
    
    print("✅ test_extract_json_from_markdown_block passed")


def test_extract_json_from_markdown_block_with_whitespace():
    """Test extracting JSON from markdown block with extra whitespace."""
    content = '''```json
    
    {"name": "Alice", "score": 95}
    
    ```'''
    result = extract_json_from_content(content)
    
    assert result["name"] == "Alice"
    assert result["score"] == 95
    
    print("✅ test_extract_json_from_markdown_block_with_whitespace passed")


def test_extract_json_from_markdown_block_multiline():
    """Test extracting multiline JSON from markdown block."""
    content = '''```json
{
  "name": "Alice",
  "age": 30,
  "scores": [95, 88, 92]
}
```'''
    result = extract_json_from_content(content)
    
    assert result["name"] == "Alice"
    assert result["age"] == 30
    assert result["scores"] == [95, 88, 92]
    
    print("✅ test_extract_json_from_markdown_block_multiline passed")


def test_extract_json_from_markdown_block_with_text_before():
    """Test extracting JSON from markdown block with text before."""
    content = '''The following is the JSON response:
```json
{"status": "success", "data": {"value": 42}}
```
That's the result.'''
    result = extract_json_from_content(content)
    
    assert result["status"] == "success"
    assert result["data"]["value"] == 42
    
    print("✅ test_extract_json_from_markdown_block_with_text_before passed")


# Strategy 3: Generic ``` code blocks
def test_extract_json_from_generic_code_block():
    """Test extracting JSON from generic code block."""
    content = '''```
{"title": "Test", "count": 5}
```'''
    result = extract_json_from_content(content)
    
    assert result["title"] == "Test"
    assert result["count"] == 5
    
    print("✅ test_extract_json_from_generic_code_block passed")


def test_extract_json_from_generic_code_block_multiple():
    """Test extracting JSON when multiple code blocks exist (should use first)."""
    content = '''```
{"first": "block"}
```
Some text
```
{"second": "block"}
```'''
    result = extract_json_from_content(content)
    
    # Should extract from first code block
    assert result["first"] == "block"
    assert "second" not in result
    
    print("✅ test_extract_json_from_generic_code_block_multiple passed")


# Strategy 4: JSON object pattern { ... }
def test_extract_json_embedded_in_text():
    """Test extracting JSON embedded in text."""
    content = 'The response is: {"key": "value", "number": 42} as requested.'
    result = extract_json_from_content(content)
    
    assert result["key"] == "value"
    assert result["number"] == 42
    
    print("✅ test_extract_json_embedded_in_text passed")


def test_extract_json_object_with_nested():
    """Test extracting nested JSON object from text."""
    content = 'Result: {"user": {"id": 123, "name": "John"}, "status": "ok"} end'
    result = extract_json_from_content(content)
    
    assert result["user"]["id"] == 123
    assert result["user"]["name"] == "John"
    assert result["status"] == "ok"
    
    print("✅ test_extract_json_object_with_nested passed")


def test_extract_json_object_with_text_after():
    """Test extracting JSON object when there's text after it."""
    content = 'Result: {"status": "ok", "value": 42} and some additional text here.'
    result = extract_json_from_content(content)
    
    assert result["status"] == "ok"
    assert result["value"] == 42
    
    print("✅ test_extract_json_object_with_text_after passed")


def test_extract_json_object_with_arrays():
    """Test extracting JSON object containing arrays."""
    content = 'Data: {"items": [1, 2, 3], "tags": ["a", "b"]}'
    result = extract_json_from_content(content)
    
    assert result["items"] == [1, 2, 3]
    assert result["tags"] == ["a", "b"]
    
    print("✅ test_extract_json_object_with_arrays passed")


# Strategy 5: JSON array pattern [ ... ]
def test_extract_json_array():
    """Test extracting JSON array."""
    content = '[{"id": 1}, {"id": 2}]'
    result = extract_json_from_content(content)
    
    assert isinstance(result, list)
    assert len(result) == 2
    
    print("✅ test_extract_json_array passed")


def test_extract_json_array_simple():
    """Test extracting simple JSON array."""
    content = 'Values: [1, 2, 3, 4, 5]'
    result = extract_json_from_content(content)
    
    assert isinstance(result, list)
    assert result == [1, 2, 3, 4, 5]
    
    print("✅ test_extract_json_array_simple passed")


def test_extract_json_array_nested():
    """Test extracting nested JSON array."""
    content = 'Nested: [[1, 2], [3, 4], [5, 6]]'
    result = extract_json_from_content(content)
    
    assert isinstance(result, list)
    assert result == [[1, 2], [3, 4], [5, 6]]
    
    print("✅ test_extract_json_array_nested passed")


# Edge cases and error handling
def test_extract_json_empty_content():
    """Test that empty content raises ValueError."""
    content = ""
    
    try:
        extract_json_from_content(content)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Empty content" in str(e)
    
    print("✅ test_extract_json_empty_content passed")


def test_extract_json_whitespace_only():
    """Test that whitespace-only content raises ValueError."""
    content = "   \n\t  "
    
    try:
        extract_json_from_content(content)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Could not extract valid JSON" in str(e)
    
    print("✅ test_extract_json_whitespace_only passed")


def test_extract_json_invalid_raises():
    """Test that invalid JSON raises ValueError."""
    content = "This is not JSON at all"
    
    try:
        extract_json_from_content(content)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Could not extract valid JSON" in str(e)
    
    print("✅ test_extract_json_invalid_raises passed")


def test_extract_json_malformed_in_code_block():
    """Test that malformed JSON in code block is skipped."""
    # Test that when code blocks have invalid JSON, it raises an error
    content = '''```json
{invalid json}
```'''
    
    try:
        extract_json_from_content(content)
        assert False, "Expected ValueError for malformed JSON"
    except ValueError as e:
        assert "Could not extract valid JSON" in str(e)
    
    print("✅ test_extract_json_malformed_in_code_block passed")


def test_extract_json_prefers_json_block_over_generic():
    """Test that ```json blocks are preferred over generic ``` blocks."""
    content = '''```
{"generic": "block"}
```
```json
{"json": "block"}
```'''
    result = extract_json_from_content(content)
    
    # Should prefer ```json block (Strategy 2 over Strategy 3)
    assert result["json"] == "block"
    assert "generic" not in result
    
    print("✅ test_extract_json_prefers_json_block_over_generic passed")


# ==================== TESTS FOR soft_parse ====================

def test_soft_parse_exact_match():
    """Test soft_parse with exact matching fields."""
    data = {"name": "John", "age": 30, "score": 95.5, "is_active": True}
    result = soft_parse(SimpleModel, data)
    
    assert result.name == "John"
    assert result.age == 30
    assert result.score == 95.5
    assert result.is_active == True
    
    print("✅ test_soft_parse_exact_match passed")


def test_soft_parse_ignores_extra_fields():
    """Test that soft_parse ignores extra fields not in model."""
    data = {
        "name": "Jane",
        "age": 25,
        "score": 88.0,
        "is_active": False,
        "extra_field": "should be ignored",
        "another_extra": 999
    }
    result = soft_parse(SimpleModel, data)
    
    assert result.name == "Jane"
    assert result.age == 25
    assert not hasattr(result, "extra_field")
    
    print("✅ test_soft_parse_ignores_extra_fields passed")


def test_soft_parse_ignores_multiple_extra_fields():
    """Test that soft_parse ignores many extra fields."""
    data = {
        "name": "Test",
        "age": 20,
        "score": 50.0,
        "is_active": True,
        "extra1": "ignored",
        "extra2": 123,
        "extra3": {"nested": "ignored"},
        "extra4": [1, 2, 3]
    }
    result = soft_parse(SimpleModel, data)
    
    assert result.name == "Test"
    assert not hasattr(result, "extra1")
    assert not hasattr(result, "extra2")
    assert not hasattr(result, "extra3")
    assert not hasattr(result, "extra4")
    
    print("✅ test_soft_parse_ignores_multiple_extra_fields passed")


def test_soft_parse_with_optional_missing():
    """Test soft_parse with missing optional fields."""
    data = {"required_field": "present"}
    result = soft_parse(ModelWithOptionals, data)
    
    assert result.required_field == "present"
    assert result.optional_string is None
    assert result.optional_int is None
    assert result.optional_with_default == "default_value"
    
    print("✅ test_soft_parse_with_optional_missing passed")


def test_soft_parse_with_optional_provided():
    """Test soft_parse with optional fields provided."""
    data = {
        "required_field": "present",
        "optional_string": "provided",
        "optional_int": 42
    }
    result = soft_parse(ModelWithOptionals, data)
    
    assert result.required_field == "present"
    assert result.optional_string == "provided"
    assert result.optional_int == 42
    assert result.optional_with_default == "default_value"
    
    print("✅ test_soft_parse_with_optional_provided passed")


def test_soft_parse_with_partial_optionals():
    """Test soft_parse with some optional fields provided."""
    data = {
        "required_field": "present",
        "optional_string": "provided"
        # optional_int is missing
    }
    result = soft_parse(ModelWithOptionals, data)
    
    assert result.required_field == "present"
    assert result.optional_string == "provided"
    assert result.optional_int is None
    
    print("✅ test_soft_parse_with_partial_optionals passed")


def test_soft_parse_nested_model():
    """Test soft_parse with nested model."""
    data = {
        "name": "Bob",
        "email": "bob@example.com",
        "address": {
            "street": "123 Main St",
            "city": "Boston",
            "zip_code": "02101"
        }
    }
    result = soft_parse(Person, data)
    
    assert result.name == "Bob"
    assert result.address.city == "Boston"
    assert result.address.street == "123 Main St"
    
    print("✅ test_soft_parse_nested_model passed")


def test_soft_parse_nested_model_with_extra():
    """Test soft_parse with nested model that has extra fields."""
    data = {
        "name": "Bob",
        "email": "bob@example.com",
        "address": {
            "street": "123 Main St",
            "city": "Boston",
            "zip_code": "02101",
            "extra_field": "ignored"
        },
        "extra_top_level": "also ignored"
    }
    result = soft_parse(Person, data)
    
    assert result.name == "Bob"
    assert result.address.city == "Boston"
    assert not hasattr(result, "extra_top_level")
    # Note: nested extra fields might still be in the dict but Pydantic will ignore them
    
    print("✅ test_soft_parse_nested_model_with_extra passed")


def test_soft_parse_nested_model_optional():
    """Test soft_parse with optional nested model."""
    data = {
        "id": "123",
        "name": "Test",
        "tags": ["a", "b"],
        "items": [{"product_name": "Widget", "quantity": 2, "unit_price": 10.0}],
        "owner": {
            "name": "Owner",
            "email": "owner@example.com",
            "address": {
                "street": "456 Oak Ave",
                "city": "Seattle",
                "zip_code": "98101"
            }
        }
    }
    result = soft_parse(ComplexModel, data)
    
    assert result.id == "123"
    assert result.owner is not None
    assert result.owner.name == "Owner"
    assert result.owner.address.city == "Seattle"
    
    print("✅ test_soft_parse_nested_model_optional passed")


def test_soft_parse_nested_model_optional_missing():
    """Test soft_parse with optional nested model missing."""
    data = {
        "id": "123",
        "name": "Test",
        "tags": ["a", "b"],
        "items": [{"product_name": "Widget", "quantity": 2, "unit_price": 10.0}]
        # owner is missing
    }
    result = soft_parse(ComplexModel, data)
    
    assert result.id == "123"
    assert result.owner is None
    
    print("✅ test_soft_parse_nested_model_optional_missing passed")


def test_soft_parse_with_lists():
    """Test soft_parse with list fields."""
    data = {
        "tags": ["python", "testing", "pydantic"],
        "scores": [95, 88, 92],
        "items": [1.5, 2.5, 3.5]
    }
    result = soft_parse(ModelWithLists, data)
    
    assert result.tags == ["python", "testing", "pydantic"]
    assert result.scores == [95, 88, 92]
    assert result.items == [1.5, 2.5, 3.5]
    
    print("✅ test_soft_parse_with_lists passed")


def test_soft_parse_with_lists_and_extra():
    """Test soft_parse with list fields and extra data."""
    data = {
        "tags": ["python", "testing"],
        "scores": [95, 88],
        "items": [1.5, 2.5],
        "extra_list": ["ignored"],
        "extra_field": "ignored"
    }
    result = soft_parse(ModelWithLists, data)
    
    assert result.tags == ["python", "testing"]
    assert not hasattr(result, "extra_list")
    assert not hasattr(result, "extra_field")
    
    print("✅ test_soft_parse_with_lists_and_extra passed")


def test_soft_parse_with_list_of_nested():
    """Test soft_parse with list of nested models."""
    data = {
        "order_id": "ORD-123",
        "customer_name": "Alice",
        "items": [
            {"product_name": "Widget", "quantity": 2, "unit_price": 10.0},
            {"product_name": "Gadget", "quantity": 1, "unit_price": 20.0}
        ],
        "total": 40.0
    }
    result = soft_parse(Order, data)
    
    assert result.order_id == "ORD-123"
    assert len(result.items) == 2
    assert result.items[0].product_name == "Widget"
    assert result.items[1].product_name == "Gadget"
    assert result.total == 40.0
    
    print("✅ test_soft_parse_with_list_of_nested passed")


def test_soft_parse_with_list_of_nested_extra():
    """Test soft_parse with list of nested models containing extra fields."""
    data = {
        "order_id": "ORD-123",
        "customer_name": "Alice",
        "items": [
            {
                "product_name": "Widget",
                "quantity": 2,
                "unit_price": 10.0,
                "extra_item_field": "ignored"
            }
        ],
        "total": 20.0,
        "extra_order_field": "ignored"
    }
    result = soft_parse(Order, data)
    
    assert len(result.items) == 1
    assert result.items[0].product_name == "Widget"
    assert not hasattr(result, "extra_order_field")
    
    print("✅ test_soft_parse_with_list_of_nested_extra passed")


def test_soft_parse_deeply_nested():
    """Test soft_parse with deeply nested structure."""
    data = {
        "level1_field": "top",
        "nested": {
            "name": "Person",
            "email": "person@example.com",
            "address": {
                "street": "789 Elm St",
                "city": "Portland",
                "zip_code": "97201"
            }
        }
    }
    result = soft_parse(DeeplyNested, data)
    
    assert result.level1_field == "top"
    assert result.nested.name == "Person"
    assert result.nested.address.city == "Portland"
    
    print("✅ test_soft_parse_deeply_nested passed")


def test_soft_parse_type_coercion_string_to_int():
    """Test soft_parse attempts type coercion (string to int)."""
    data = {
        "name": "Test",
        "age": "30",  # String instead of int
        "score": 95.5,
        "is_active": True
    }
    result = soft_parse(SimpleModel, data)
    
    # Pydantic should attempt coercion
    assert result.age == 30  # Should be coerced to int
    assert isinstance(result.age, int)
    
    print("✅ test_soft_parse_type_coercion_string_to_int passed")


def test_soft_parse_type_coercion_string_to_float():
    """Test soft_parse attempts type coercion (string to float)."""
    data = {
        "name": "Test",
        "age": 30,
        "score": "95.5",  # String instead of float
        "is_active": True
    }
    result = soft_parse(SimpleModel, data)
    
    # Pydantic should attempt coercion
    assert result.score == 95.5
    assert isinstance(result.score, float)
    
    print("✅ test_soft_parse_type_coercion_string_to_float passed")


def test_soft_parse_type_coercion_bool():
    """Test soft_parse attempts type coercion for boolean."""
    data = {
        "name": "Test",
        "age": 30,
        "score": 95.5,
        "is_active": "true"  # String instead of bool
    }
    result = soft_parse(SimpleModel, data)
    
    # Pydantic should attempt coercion
    assert result.is_active == True
    assert isinstance(result.is_active, bool)
    
    print("✅ test_soft_parse_type_coercion_bool passed")


def test_soft_parse_with_dict_metadata():
    """Test soft_parse with Optional[Dict] field."""
    data = {
        "id": "123",
        "name": "Test",
        "tags": ["a", "b"],
        "items": [{"product_name": "Widget", "quantity": 1, "unit_price": 10.0}],
        "metadata": {"key1": "value1", "key2": "value2"}
    }
    result = soft_parse(ComplexModel, data)
    
    assert result.metadata is not None
    assert result.metadata["key1"] == "value1"
    assert result.metadata["key2"] == "value2"
    
    print("✅ test_soft_parse_with_dict_metadata passed")


def test_soft_parse_with_dict_metadata_missing():
    """Test soft_parse with Optional[Dict] field missing."""
    data = {
        "id": "123",
        "name": "Test",
        "tags": ["a", "b"],
        "items": [{"product_name": "Widget", "quantity": 1, "unit_price": 10.0}]
        # metadata is missing
    }
    result = soft_parse(ComplexModel, data)
    
    assert result.metadata is None
    
    print("✅ test_soft_parse_with_dict_metadata_missing passed")


# ==================== TESTS FOR soft_parse SAFETY FALLBACK ====================

def test_soft_parse_missing_required_field():
    """Test soft_parse returns partial data when required field is missing."""
    data = {
        "name": "Partial",
        # "age" is missing (required)
        "score": 85.0,
        "is_active": True
    }
    result = soft_parse(SimpleModel, data)
    
    # Should still return what we have
    assert result.name == "Partial"
    assert result.score == 85.0
    assert result.is_active == True
    # Missing required field should be None (filled in by soft_parse)
    assert result.age is None
    
    print("✅ test_soft_parse_missing_required_field passed")


def test_soft_parse_missing_multiple_required_fields():
    """Test soft_parse returns partial data when multiple required fields are missing."""
    data = {
        "name": "OnlyName"
        # "age", "score", "is_active" are all missing (required)
    }
    result = soft_parse(SimpleModel, data)
    
    # Should still return what we have
    assert result.name == "OnlyName"
    # Missing required fields should be None (filled in by soft_parse)
    assert result.age is None
    assert result.score is None
    assert result.is_active is None
    
    print("✅ test_soft_parse_missing_multiple_required_fields passed")


def test_soft_parse_empty_data():
    """Test soft_parse handles empty data gracefully."""
    data = {}
    result = soft_parse(SimpleModel, data)
    
    # All fields should be None (filled in by soft_parse)
    assert result.name is None
    assert result.age is None
    assert result.score is None
    assert result.is_active is None
    
    print("✅ test_soft_parse_empty_data passed")


def test_soft_parse_nested_missing_required():
    """Test soft_parse with nested model missing required fields."""
    data = {
        "name": "Bob",
        # "email" is missing (required)
        "address": {
            "street": "123 Main St",
            # "city" is missing (required)
            "zip_code": "02101"
        }
    }
    result = soft_parse(Person, data)
    
    # Should return what we have
    assert result.name == "Bob"
    assert result.email is None  # Filled in by soft_parse
    # Nested model may have partial data
    assert result.address is not None
    
    print("✅ test_soft_parse_nested_missing_required passed")


def test_soft_parse_partial_list_items():
    """Test soft_parse with list items missing required fields."""
    data = {
        "order_id": "ORD-PARTIAL",
        # "customer_name" is missing (required)
        "items": [
            {"product_name": "Widget", "quantity": 2}  # unit_price missing
        ],
        "total": 20.0
    }
    result = soft_parse(Order, data)
    
    # Should return what we have
    assert result.order_id == "ORD-PARTIAL"
    assert result.customer_name is None  # Filled in by soft_parse
    assert result.total == 20.0
    assert len(result.items) == 1
    # When model_construct is used, nested items may be dicts
    item = result.items[0]
    if isinstance(item, dict):
        assert item["product_name"] == "Widget"
    else:
        assert item.product_name == "Widget"
    
    print("✅ test_soft_parse_partial_list_items passed")


def test_soft_parse_invalid_type_falls_back():
    """Test soft_parse falls back when type coercion fails."""
    data = {
        "name": "Test",
        "age": "not_a_number",  # Can't coerce to int
        "score": 85.0,
        "is_active": True
    }
    result = soft_parse(SimpleModel, data)
    
    # Should still return data (fallback to model_construct)
    assert result.name == "Test"
    assert result.score == 85.0
    assert result.is_active == True
    # The invalid value is kept as-is since model_construct bypasses validation
    assert result.age == "not_a_number"
    
    print("✅ test_soft_parse_invalid_type_falls_back passed")


# ==================== TESTS FOR soft_parse WITH default_factory ====================

def test_soft_parse_default_factory_list():
    """Test soft_parse respects default_factory=list for missing fields."""
    data = {"name": "Test"}
    result = soft_parse(ModelWithDefaultFactory, data)
    
    assert result.name == "Test"
    assert isinstance(result.items, list), f"Expected list, got {type(result.items)}"
    assert result.items == [], f"Expected empty list, got {result.items}"
    
    print("✅ test_soft_parse_default_factory_list passed")


def test_soft_parse_default_factory_dict():
    """Test soft_parse respects default_factory=dict for missing fields."""
    data = {"name": "Test"}
    result = soft_parse(ModelWithDefaultFactory, data)
    
    assert isinstance(result.metadata, dict), f"Expected dict, got {type(result.metadata)}"
    assert result.metadata == {}, f"Expected empty dict, got {result.metadata}"
    
    print("✅ test_soft_parse_default_factory_dict passed")


def test_soft_parse_default_factory_lambda():
    """Test soft_parse respects default_factory with lambda for missing fields."""
    data = {"name": "Test"}
    result = soft_parse(ModelWithDefaultFactory, data)
    
    assert isinstance(result.count, int), f"Expected int, got {type(result.count)}"
    assert result.count == 0, f"Expected 0, got {result.count}"
    
    print("✅ test_soft_parse_default_factory_lambda passed")


def test_soft_parse_default_factory_mixed():
    """Test soft_parse with model mixing default and default_factory."""
    data = {"name": "Test"}
    result = soft_parse(ModelWithMixedDefaults, data)
    
    assert result.name == "Test"
    assert isinstance(result.items, list), f"Expected list, got {type(result.items)}"
    assert result.items == [], f"Expected empty list, got {result.items}"
    assert result.optional_field is None
    assert result.field_with_default == "default_value"
    
    print("✅ test_soft_parse_default_factory_mixed passed")


def test_soft_parse_default_factory_provided_value():
    """Test soft_parse uses provided value over default_factory."""
    data = {"name": "Test", "items": [1, 2, 3], "metadata": {"key": "value"}}
    result = soft_parse(ModelWithDefaultFactory, data)
    
    assert result.name == "Test"
    assert result.items == [1, 2, 3], "Should use provided value, not factory"
    assert result.metadata == {"key": "value"}, "Should use provided value, not factory"
    
    print("✅ test_soft_parse_default_factory_provided_value passed")


def test_soft_parse_default_factory_partial_missing():
    """Test soft_parse when some default_factory fields are missing."""
    data = {"name": "Test", "items": [1, 2, 3]}
    # metadata and count are missing, should use default_factory
    result = soft_parse(ModelWithDefaultFactory, data)
    
    assert result.items == [1, 2, 3]
    assert isinstance(result.metadata, dict)
    assert result.metadata == {}
    assert isinstance(result.count, int)
    assert result.count == 0
    
    print("✅ test_soft_parse_default_factory_partial_missing passed")


# ==================== TESTS FOR parse_json_response ====================

def test_parse_json_response_simple():
    """Test parse_json_response with simple JSON."""
    content = '{"name": "Test", "age": 42, "score": 99.9, "is_active": true}'
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Test"
    assert result.age == 42
    assert result.score == 99.9
    assert result.is_active == True
    
    print("✅ test_parse_json_response_simple passed")


def test_parse_json_response_with_extras():
    """Test parse_json_response ignores extra fields."""
    content = '{"name": "Test", "age": 42, "score": 99.9, "is_active": true, "extra": "ignored"}'
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Test"
    assert result.age == 42
    assert not hasattr(result, "extra")
    
    print("✅ test_parse_json_response_with_extras passed")


def test_parse_json_response_from_markdown():
    """Test parse_json_response extracts from markdown."""
    content = '''Here's the extracted data:
```json
{"name": "Markdown", "age": 10, "score": 50.0, "is_active": false}
```
'''
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Markdown"
    assert result.age == 10
    assert result.is_active == False
    
    print("✅ test_parse_json_response_from_markdown passed")


def test_parse_json_response_from_generic_code_block():
    """Test parse_json_response extracts from generic code block."""
    content = '''```
{"name": "Generic", "age": 25, "score": 75.0, "is_active": true}
```'''
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Generic"
    assert result.age == 25
    
    print("✅ test_parse_json_response_from_generic_code_block passed")


def test_parse_json_response_embedded_in_text():
    """Test parse_json_response extracts JSON embedded in text."""
    content = 'The result is: {"name": "Embedded", "age": 30, "score": 80.0, "is_active": true} here.'
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Embedded"
    assert result.age == 30
    
    print("✅ test_parse_json_response_embedded_in_text passed")


def test_parse_json_response_with_nested_model():
    """Test parse_json_response with nested model."""
    content = '''```json
{
  "name": "Alice",
  "email": "alice@example.com",
  "address": {
    "street": "123 Main St",
    "city": "Boston",
    "zip_code": "02101"
  }
}
```'''
    result = parse_json_response(content, Person, "test-model")
    
    assert result.name == "Alice"
    assert result.email == "alice@example.com"
    assert result.address.city == "Boston"
    assert result.address.street == "123 Main St"
    
    print("✅ test_parse_json_response_with_nested_model passed")


def test_parse_json_response_with_nested_model_extra():
    """Test parse_json_response with nested model and extra fields."""
    content = '''{
  "name": "Bob",
  "email": "bob@example.com",
  "address": {
    "street": "456 Oak Ave",
    "city": "Seattle",
    "zip_code": "98101",
    "extra_address_field": "ignored"
  },
  "extra_top_field": "ignored"
}'''
    result = parse_json_response(content, Person, "test-model")
    
    assert result.name == "Bob"
    assert result.address.city == "Seattle"
    assert not hasattr(result, "extra_top_field")
    
    print("✅ test_parse_json_response_with_nested_model_extra passed")


def test_parse_json_response_with_optionals():
    """Test parse_json_response with optional fields."""
    content = '{"required_field": "present", "optional_string": "provided"}'
    result = parse_json_response(content, ModelWithOptionals, "test-model")
    
    assert result.required_field == "present"
    assert result.optional_string == "provided"
    assert result.optional_int is None
    assert result.optional_with_default == "default_value"
    
    print("✅ test_parse_json_response_with_optionals passed")


def test_parse_json_response_with_optionals_missing():
    """Test parse_json_response with missing optional fields."""
    content = '{"required_field": "present"}'
    result = parse_json_response(content, ModelWithOptionals, "test-model")
    
    assert result.required_field == "present"
    assert result.optional_string is None
    assert result.optional_int is None
    
    print("✅ test_parse_json_response_with_optionals_missing passed")


def test_parse_json_response_with_lists():
    """Test parse_json_response with list fields."""
    content = '''```json
{
  "tags": ["python", "testing", "pydantic"],
  "scores": [95, 88, 92],
  "items": [1.5, 2.5, 3.5]
}
```'''
    result = parse_json_response(content, ModelWithLists, "test-model")
    
    assert result.tags == ["python", "testing", "pydantic"]
    assert result.scores == [95, 88, 92]
    assert result.items == [1.5, 2.5, 3.5]
    
    print("✅ test_parse_json_response_with_lists passed")


def test_parse_json_response_with_list_of_nested():
    """Test parse_json_response with list of nested models."""
    content = '''{
  "order_id": "ORD-456",
  "customer_name": "Charlie",
  "items": [
    {"product_name": "Widget", "quantity": 2, "unit_price": 10.0},
    {"product_name": "Gadget", "quantity": 1, "unit_price": 20.0}
  ],
  "total": 40.0
}'''
    result = parse_json_response(content, Order, "test-model")
    
    assert result.order_id == "ORD-456"
    assert result.customer_name == "Charlie"
    assert len(result.items) == 2
    assert result.items[0].product_name == "Widget"
    assert result.items[1].product_name == "Gadget"
    assert result.total == 40.0
    
    print("✅ test_parse_json_response_with_list_of_nested passed")


def test_parse_json_response_complex_model():
    """Test parse_json_response with complex model."""
    content = '''```json
{
  "id": "COMP-123",
  "name": "Complex",
  "tags": ["tag1", "tag2"],
  "metadata": {"key": "value"},
  "owner": {
    "name": "Owner",
    "email": "owner@example.com",
    "address": {
      "street": "789 Elm St",
      "city": "Portland",
      "zip_code": "97201"
    }
  },
  "items": [
    {"product_name": "Product", "quantity": 1, "unit_price": 15.0}
  ]
}
```'''
    result = parse_json_response(content, ComplexModel, "test-model")
    
    assert result.id == "COMP-123"
    assert result.name == "Complex"
    assert result.tags == ["tag1", "tag2"]
    assert result.metadata["key"] == "value"
    assert result.owner.name == "Owner"
    assert result.owner.address.city == "Portland"
    assert len(result.items) == 1
    assert result.items[0].product_name == "Product"
    
    print("✅ test_parse_json_response_complex_model passed")


def test_parse_json_response_type_coercion():
    """Test parse_json_response with type coercion."""
    content = '{"name": "Coerced", "age": "42", "score": "99.9", "is_active": "true"}'
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Coerced"
    assert result.age == 42
    assert isinstance(result.age, int)
    assert result.score == 99.9
    assert isinstance(result.score, float)
    assert result.is_active == True
    assert isinstance(result.is_active, bool)
    
    print("✅ test_parse_json_response_type_coercion passed")


def test_parse_json_response_multiline_markdown():
    """Test parse_json_response with multiline JSON in markdown."""
    content = '''Here is the response:
```json
{
  "name": "Multiline",
  "age": 35,
  "score": 87.5,
  "is_active": true
}
```
That's all.'''
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "Multiline"
    assert result.age == 35
    assert result.score == 87.5
    
    print("✅ test_parse_json_response_multiline_markdown passed")


def test_parse_json_response_with_array_takes_first():
    """Test parse_json_response handles JSON array by taking first element."""
    content = '[{"name": "First", "age": 25, "score": 85.0, "is_active": true}, {"name": "Second", "age": 30, "score": 90.0, "is_active": false}]'
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "First"
    assert result.age == 25
    assert result.score == 85.0
    assert result.is_active is True
    
    print("✅ test_parse_json_response_with_array_takes_first passed")


def test_parse_json_response_with_array_in_markdown():
    """Test parse_json_response handles JSON array in markdown code block."""
    content = '''```json
[{"name": "ArrayItem", "age": 42, "score": 99.9, "is_active": true}]
```'''
    result = parse_json_response(content, SimpleModel, "test-model")
    
    assert result.name == "ArrayItem"
    assert result.age == 42
    assert result.score == 99.9
    
    print("✅ test_parse_json_response_with_array_in_markdown passed")


def test_parse_json_response_empty_array_raises():
    """Test parse_json_response raises clear error for empty array."""
    content = '[]'
    try:
        parse_json_response(content, SimpleModel, "test-model")
        assert False, "Should have raised ValueError for empty array"
    except ValueError as e:
        assert "empty array" in str(e).lower() or "array" in str(e).lower()
        assert "SimpleModel" in str(e) or "object" in str(e).lower()
    
    print("✅ test_parse_json_response_empty_array_raises passed")


def test_parse_json_response_array_with_non_object_raises():
    """Test parse_json_response raises clear error for array with non-object elements."""
    content = '[1, 2, 3]'
    try:
        parse_json_response(content, SimpleModel, "test-model")
        assert False, "Should have raised ValueError for array with non-object elements"
    except ValueError as e:
        assert "object" in str(e).lower() or "array" in str(e).lower()
    
    print("✅ test_parse_json_response_array_with_non_object_raises passed")


# ==================== RUN ALL TESTS ====================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing extract_json_from_content")
    print("="*60)
    # Strategy 1: Pure JSON
    test_extract_pure_json()
    test_extract_pure_json_with_whitespace()
    test_extract_pure_json_complex()
    test_extract_pure_json_array()
    # Strategy 2: ```json code blocks
    test_extract_json_from_markdown_block()
    test_extract_json_from_markdown_block_with_whitespace()
    test_extract_json_from_markdown_block_multiline()
    test_extract_json_from_markdown_block_with_text_before()
    # Strategy 3: Generic ``` code blocks
    test_extract_json_from_generic_code_block()
    test_extract_json_from_generic_code_block_multiple()
    # Strategy 4: JSON object pattern
    test_extract_json_embedded_in_text()
    test_extract_json_object_with_nested()
    test_extract_json_object_with_text_after()
    test_extract_json_object_with_arrays()
    # Strategy 5: JSON array pattern
    test_extract_json_array()
    test_extract_json_array_simple()
    test_extract_json_array_nested()
    # Edge cases
    test_extract_json_empty_content()
    test_extract_json_whitespace_only()
    test_extract_json_invalid_raises()
    test_extract_json_malformed_in_code_block()
    test_extract_json_prefers_json_block_over_generic()
    
    print("\n" + "="*60)
    print("Testing soft_parse")
    print("="*60)
    test_soft_parse_exact_match()
    test_soft_parse_ignores_extra_fields()
    test_soft_parse_ignores_multiple_extra_fields()
    test_soft_parse_with_optional_missing()
    test_soft_parse_with_optional_provided()
    test_soft_parse_with_partial_optionals()
    test_soft_parse_nested_model()
    test_soft_parse_nested_model_with_extra()
    test_soft_parse_nested_model_optional()
    test_soft_parse_nested_model_optional_missing()
    test_soft_parse_with_lists()
    test_soft_parse_with_lists_and_extra()
    test_soft_parse_with_list_of_nested()
    test_soft_parse_with_list_of_nested_extra()
    test_soft_parse_deeply_nested()
    test_soft_parse_type_coercion_string_to_int()
    test_soft_parse_type_coercion_string_to_float()
    test_soft_parse_type_coercion_bool()
    test_soft_parse_with_dict_metadata()
    test_soft_parse_with_dict_metadata_missing()
    
    print("\n" + "="*60)
    print("Testing soft_parse safety fallback")
    print("="*60)
    test_soft_parse_missing_required_field()
    test_soft_parse_missing_multiple_required_fields()
    test_soft_parse_empty_data()
    test_soft_parse_nested_missing_required()
    test_soft_parse_partial_list_items()
    test_soft_parse_invalid_type_falls_back()
    
    print("\n" + "="*60)
    print("Testing soft_parse with default_factory")
    print("="*60)
    test_soft_parse_default_factory_list()
    test_soft_parse_default_factory_dict()
    test_soft_parse_default_factory_lambda()
    test_soft_parse_default_factory_mixed()
    test_soft_parse_default_factory_provided_value()
    test_soft_parse_default_factory_partial_missing()
    
    print("\n" + "="*60)
    print("Testing parse_json_response")
    print("="*60)
    test_parse_json_response_simple()
    test_parse_json_response_with_extras()
    test_parse_json_response_from_markdown()
    test_parse_json_response_from_generic_code_block()
    test_parse_json_response_embedded_in_text()
    test_parse_json_response_with_nested_model()
    test_parse_json_response_with_nested_model_extra()
    test_parse_json_response_with_optionals()
    test_parse_json_response_with_optionals_missing()
    test_parse_json_response_with_lists()
    test_parse_json_response_with_list_of_nested()
    test_parse_json_response_complex_model()
    test_parse_json_response_type_coercion()
    test_parse_json_response_multiline_markdown()
    test_parse_json_response_with_array_takes_first()
    test_parse_json_response_with_array_in_markdown()
    test_parse_json_response_empty_array_raises()
    test_parse_json_response_array_with_non_object_raises()
    
    print("\n" + "="*60)
    print("🎉 All JSON extraction/parsing tests passed!")
    print("="*60)

