# WaveAssist Python SDK 🌊

WaveAssist makes it simple to store and retrieve data in your WaveAssist.io workflows.

---

## ✨ Features

- 🔐 Simple `init()` to connect with your project
- 📦 Store and retrieve data (DataFrames, JSON, or strings)
- 🧠 LLM-friendly function names (`init`, `store_data`, `fetch_data`)
- 📁 Auto-serialization for common Python objects
- ✅ Ready for integration with any workflow or script

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

waveassist.init(
    token="your-api-token-or-uid",
    project_key="your-project-id",
    environment_key="optional-env"  # defaults to <project_key>_default
)
```

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

- String roundtrip
- JSON/dict roundtrip
- DataFrame roundtrip
- Error case when `init()` is missing

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

- Data is stored in your backend (MongoDB) as serialized strings (JSON, CSV, etc.)
- `store_data()` auto-detects the type of the object and serializes accordingly
- `fetch_data()` deserializes and returns the proper Python object

---

## 🤝 Contributing

Want to add new features/formats or integrations? PRs welcome!

---

## 🧠 Example Use Case

```python
import waveassist
waveassist.init("my-token", "project123")

# Store GitHub PR data from an automation job
waveassist.store_data("latest_pr", {
    "title": "Fix bug in auth",
    "author": "alice",
    "status": "open"
})

# Later, fetch it for processing
pr = waveassist.fetch_data("latest_pr")
print(pr["title"])
```

---

## 📬 Contact

Need help or have feedback? Reach out at [connect@waveassist.io] or open an issue.

---
© 2025 WaveAssist
