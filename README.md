# WaveAssist SDK & CLI 🌊

WaveAssist SDK makes it simple to store and retrieve data in your automation workflows. Access your projects through our Python SDK or CLI.

---

## ✨ Features

* 🔐 One-line `init()` to connect with your [WaveAssist](https://waveassist.io) project
* ⚙️ Automatically works on local and [WaveAssist Cloud](https://waveassist.io) (worker) environments
* 📦 Store and retrieve data (DataFrames, JSON, strings)
* 🧠 LLM-friendly function names (`init`, `store_data`, `fetch_data`)
* 📁 Auto-serialization for common Python objects
* 🖥️ Command-line interface for project management
* ✅ Built for automation workflows, cron jobs, and AI pipelines

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

# Will auto-resolve from:
# 1. Explicit args (if passed)
# 2. .env file (WA_UID, WA_PROJECT_KEY, WA_ENV_KEY)
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

* Data is stored in your [WaveAssist backend](https://waveassist.io) (e.g. MongoDB) as serialized content
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

Need help or have feedback? Reach out at [connect@waveassist.io](mailto:connect@waveassist.io), visit [WaveAssist.io](https://waveassist.io), or open an issue.

---

© 2025 [WaveAssist](https://waveassist.io)

