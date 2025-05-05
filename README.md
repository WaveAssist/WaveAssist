Here's the updated **README** reflecting the new flexible `init()` behavior, `.env` support, and auto-resolution flow:

---

````markdown
# WaveAssist Python SDK 🌊

WaveAssist makes it simple to store and retrieve data in your WaveAssist.io workflows.

---

## ✨ Features

- 🔐 One-line `init()` to connect with your project
- ⚙️ Automatically works on local and cloud (worker) environments
- 📦 Store and retrieve data (DataFrames, JSON, strings)
- 🧠 LLM-friendly function names (`init`, `store_data`, `fetch_data`)
- 📁 Auto-serialization for common Python objects
- ✅ Built for automation workflows, cron jobs, and AI pipelines

---

## 🚀 Getting Started

### 1. Install

```bash
pip install waveassist
````

---

### 2. Initialize the SDK

```python
import waveassist

# Option 1: Use no arguments (recommended)
waveassist.init()

# Will auto-resolve from:
# 1. Explicit args (if passed)
# 2. .env file (WA_UID, WA_PROJECT_KEY, WA_ENV_KEY)
# 3. Worker-injected credentials (on WaveAssist cloud)

# Option 2: Use explicit arguments
waveassist.init(
    token="your-user-id-or-api-token",
    project_key="your-project-id",
    environment_key="optional-env"  # Defaults to <project_key>_default
)
```

#### 🛠 Setting up `.env` (for local runs)

```env
uid=your-user-id
project_key=your-project-key

#optional
environment_key=your-env-key  # optional
```

This file will be ignored by Git if you use our default `.gitignore`.

---

### 3. Store Data

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

---

### 4. Fetch Data

```python
result = waveassist.fetch_data("user_scores")

# Will return:
# - A DataFrame (if stored as one)
# - A dict/list (if stored as JSON)
# - A string (if stored as text)
```

---

## 🧪 Running Tests

If you’re not using `pytest`, just run the test script directly:

```bash
python tests/run_tests.py
```

✅ Includes tests for:

* String roundtrip
* JSON/dict roundtrip
* DataFrame roundtrip
* Error if `init()` is not called

---

## 🛠 Project Structure

```
WaveAssist/
├── waveassist/
│   ├── __init__.py          # init(), store_data(), fetch_data()
│   ├── _config.py           # Global config vars
│   └── ...
├── tests/
│   └── run_tests.py         # Manual test runner
```

---

## 📌 Notes

* Data is stored in your WaveAssist backend (e.g. MongoDB) as serialized content
* `store_data()` auto-detects the object type and serializes it (CSV/JSON/text)
* `fetch_data()` deserializes it back to the right Python object

---

## 🧠 Example Use Case

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

---


## 🤝 Contributing

Want to add formats, features, or cloud extensions? PRs welcome!

---

## 📬 Contact

Need help or have feedback? Reach out at [connect@waveassist.io](mailto:connect@waveassist.io) or open an issue.

---

© 2025 WaveAssist
