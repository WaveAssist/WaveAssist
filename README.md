# WaveAssist SDK & CLI 🌊

WaveAssist SDK makes it simple to store and retrieve data in your automation workflows. Access your projects through our Python SDK or CLI.

---

## ✨ Features

- 🔐 One-line `init()` to connect with your [WaveAssist](https://waveassist.io) project
- ⚙️ Automatically works on local and [WaveAssist Cloud](https://waveassist.io) (worker) environments
- 📦 Store and retrieve data (DataFrames, JSON, strings)
- 🧠 LLM-friendly function names (`init`, `store_data`, `fetch_data`)
- 📁 Auto-serialization for common Python objects
- 🤖 LLM integration with structured outputs via Instructor and OpenRouter
- 💳 Credit management and automatic email notifications
- 🖥️ Command-line interface for project management
- ✅ Built for automation workflows, cron jobs, and AI pipelines

---

## 🚀 Getting Started

### 1. Install

```bash
pip install waveassist
```

---

### 2. Initialize the SDK

```python
import waveassist

# Option 1: Use no arguments (recommended)
waveassist.init()

# Option 2: With explicit parameters
waveassist.init(
    token="your-user-id",
    project_key="your-project-key",
    environment_key="your-env-key",  # optional
    run_id="run-123",  # optional
    check_credits=True  # optional: raises RuntimeError if credits_available is "0"
)

# When check_credits=True, a missing credits_available key is treated as credits available (default "1").
# Will auto-resolve from:
# 1. Explicit args (if passed)
# 2. .env file (uid, project_key, environment_key)
# 3. Worker-injected credentials (on [WaveAssist Cloud](https://waveassist.io))
```

#### 🛠 Setting up `.env` (for local runs)

```env
uid=your-user-id
project_key=your-project-key

# optional
environment_key=your-env-key
```

This file will be ignored by Git if you use our default `.gitignore`.

---

### 3. Store Data

Data is serialized by type. You can rely on type-safe storage and retrieval.

#### 🧾 Store a string

```python
waveassist.store_data("welcome_message", "Hello, world!")
```

#### 📊 Store a DataFrame

```python
import pandas as pd

df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 88]})
waveassist.store_data("user_scores", df)
```

#### 🧠 Store JSON/dict/array

```python
profile = {"name": "Alice", "age": 30}
waveassist.store_data("profile_data", profile)
```

#### 📌 Optional: Force storage type

Store data as a specific type regardless of input:

```python
# Store a dict as a string
waveassist.store_data("config", {"a": 1}, data_type="string")

# Store a string as JSON (wraps as {"value": "..."})
waveassist.store_data("greeting", "Hello", data_type="json")
```

**Parameters:** `store_data(key, data, run_based=False, data_type=None)`. Use `data_type="string"`, `"json"`, or `"dataframe"` to force that storage type.

---

### 4. Fetch Data

```python
result = waveassist.fetch_data("user_scores")

# Returns the correct type:
# - pd.DataFrame (if stored as dataframe)
# - dict or list (if stored as JSON)
# - str (if stored as string)
```

**Use a default when the key might be missing:**

```python
# Return a default if key is missing or API fails
count = waveassist.fetch_data("failure_count", default=0)
greeting = waveassist.fetch_data("welcome", default="Hello")
df = waveassist.fetch_data("results", default=pd.DataFrame())  # empty DataFrame
```

**Parameters:** `fetch_data(key, run_based=False, default=None)`.

---

### 5. Send Email

Send emails (e.g. for notifications) via the WaveAssist backend:

```python
waveassist.send_email(
    subject="Daily report",
    html_content="<p>Summary: ...</p>",
    attachment_file=open("report.pdf", "rb"),  # optional
    raise_on_failure=True  # default: raise WaveAssistEmailError on validation or API failure
)
```

- **Validation:** Subject and HTML body must be non-empty (and within length limits). Attachments must be file-like with a `.read()` method.
- **Retry:** The SDK retries the send once on transient failure.
- **Errors:** By default, validation failures raise `ValueError` and API failures raise `RuntimeError`. Pass `raise_on_failure=False` to return `False` instead.

---

### 6. Check Credits and Notify

Check OpenRouter credits and automatically send email notifications if insufficient credits are available:

```python
# Check if you have enough credits for an operation
has_credits = waveassist.check_credits_and_notify(
    required_credits=10.5,
    assistant_name="WavePredict"
)

if has_credits:
    # Proceed with your operation
    print("Credits available, proceeding...")
else:
    # Credits insufficient - email notification sent (max 3 times)
    print("Insufficient credits, operation skipped")
```

**Features:**

- Automatically checks OpenRouter credit balance
- Sends email notification if credits are insufficient (max 3 times)
- Resets notification count when credits become sufficient
- Stores credit availability status for workflow control

---

### 7. Call LLM with Structured Outputs

Get structured responses from LLMs via OpenRouter with Pydantic models:

```python
from pydantic import BaseModel

# Define your response structure
class UserInfo(BaseModel):
    name: str
    age: int
    email: str

# Call LLM with structured output
result = waveassist.call_llm(
    model="gpt-4o",
    prompt="Extract user info: John Doe, 30, john@example.com",
    response_model=UserInfo
)

print(result.name)  # "John Doe"
print(result.age)    # 30
print(result.email)  # "john@example.com"
```

**Setup:**

1. Store your OpenRouter API key:

```python
waveassist.store_data('open_router_key', 'your_openrouter_api_key')
```

2. Use `call_llm()` with any Pydantic model for structured outputs

**Advanced Usage:**

```python
result = waveassist.call_llm(
    model="anthropic/claude-3-opus",
    prompt="Analyze this data...",
    response_model=MyModel,
    should_retry=True,  # retry once on JSON/format errors
    max_tokens=3000,
    extra_body={"web_search_options": {"search_context_size": "medium"}}
)
```

**Errors:** `RuntimeError` (API/network failure), `ValueError` (invalid or non-JSON response). Transport errors are retried once automatically.

---

## 🖥️ Command Line Interface

WaveAssist CLI comes bundled with the Python package. After installation, you can use the following commands:

### 🔑 Authentication

```bash
waveassist login
```

This will open your browser for authentication and store the token locally.

### 📤 Push Code

```bash
waveassist push PROJECT_KEY [--force]
```

Push your local Python code to a WaveAssist project.

### 📥 Pull Code

```bash
waveassist pull PROJECT_KEY [--force]
```

Pull Python code from a WaveAssist project to your local machine.

### ℹ️ Version Info

```bash
waveassist version
```

Display CLI version and environment information.

---

## 🧪 Running Tests

Run with pytest (recommended) or the test scripts:

```bash
# All tests (use project Python if you have a venv)
python -m pytest tests/ -v

# Or run modules directly
python tests/test_core.py
python tests/test_json_generate.py
python tests/test_json_extract.py
```

✅ Includes tests for:

- String, JSON, and DataFrame roundtrips; `store_data` with explicit `data_type`; `fetch_data` with `default`
- `send_email` validation, attachments, and `raise_on_failure`
- Error handling when `init()` is not called (`RuntimeError`)
- Environment variable and `.env` file resolution
- JSON template generation for Pydantic models
- JSON extraction from various formats (pure JSON, markdown code blocks, embedded text)
- Soft parsing with missing required fields (safety fallback for LLM responses)
- Type coercion and nested model handling

---

## 🛠 Project Structure

```
WaveAssist/
├── waveassist/
│   ├── __init__.py          # Public API: init(), store_data(), fetch_data(), send_email(),
│   │                         # check_credits_and_notify(), call_llm()
│   ├── _config.py            # Global config and version
│   ├── constants.py         # API_BASE_URL, OpenRouter, dashboard URLs
│   ├── utils.py             # API helpers, JSON parsing, soft_parse, exception classes
│   ├── core.py              # CLI: login, pull, push (uses constants for URLs)
│   └── cli.py               # Command-line entry (waveassist login/push/pull/version)
├── tests/
│   ├── test_core.py         # Core SDK + send_email tests
│   ├── test_json_generate.py # JSON template generation tests
│   ├── test_json_extract.py  # JSON extraction/parsing tests
│   └── test_llm_call.py     # call_llm integration tests (skipped without API key)
```

---

## 📌 Notes

- Data is stored in your [WaveAssist backend](https://waveassist.io) (e.g. MongoDB) as serialized content
- `store_data()` auto-detects the object type and serializes it (dataframe/JSON/string), or use `data_type` to force a type
- `fetch_data()` returns the correct Python type and supports a `default` when the key is missing or the API fails
- **Logging:** The SDK uses the standard library `logging` module (logger name `"waveassist"`). Configure level or handlers to control or suppress SDK messages (e.g. `logging.getLogger("waveassist").setLevel(logging.WARNING)`).
- **Errors:** The SDK raises standard exceptions: **`ValueError`** for bad or missing input (e.g. missing uid/project_key in init, email validation, OpenRouter key not found, LLM JSON/format failure) and **`RuntimeError`** for invalid state or API failures (e.g. not initialized, credits not available, send email failed, LLM API/network failure). Catch `ValueError` or `RuntimeError` (or `Exception`) as needed.

---

## 🧠 Example Use Cases

### Basic Data Storage

```python
import waveassist
waveassist.init()  # Auto-initialized from .env or worker

# Store GitHub PR data
waveassist.store_data("latest_pr", {
    "title": "Fix bug in auth",
    "author": "alice",
    "status": "open"
})

# Later, fetch it for further processing
pr = waveassist.fetch_data("latest_pr")
print(pr["title"])
```

### LLM Integration with Credit Management

```python
import waveassist
from pydantic import BaseModel

waveassist.init()

# Store OpenRouter API key
waveassist.store_data('open_router_key', 'your_api_key')

# Check credits before expensive operation
required_credits = 5.0
if waveassist.check_credits_and_notify(required_credits, "MyAssistant"):
    # Use LLM with structured output
    class AnalysisResult(BaseModel):
        summary: str
        confidence: float
        recommendations: list[str]

    result = waveassist.call_llm(
        model="gpt-4o",
        prompt="Analyze this data and provide recommendations...",
        response_model=AnalysisResult
    )

    # Store the structured result
    waveassist.store_data("analysis_result", result.dict())
```

---

## 🤝 Contributing

Want to add formats, features, or cloud extensions? PRs welcome!

---

## 📬 Contact

Need help or have feedback? Reach out at [connect@waveassist.io](mailto:connect@waveassist.io), visit [WaveAssist.io](https://waveassist.io), or open an issue.

---

© 2025 [WaveAssist](https://waveassist.io)
