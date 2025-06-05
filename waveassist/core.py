import argparse
import json
import os
import sys
import uuid
import time
import webbrowser
import requests
from pathlib import Path
import zipfile
import tempfile
import shutil


CONFIG_PATH = Path.home() / ".waveassist" / "config.json"
API_BASE_URL = "https://api.waveassist.io"
DASHBOARD_URL = "https://app.waveassist.io"

def save_token(uid: str):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"uid": uid}, f)
    print("✅ Logged in and saved to ~/.waveassist/config.json")

def login():
    session_id = str(uuid.uuid4())
    login_url = f"{DASHBOARD_URL}/login?session_id={session_id}"
    print("🔐 Opening browser for login...")
    webbrowser.open(login_url)

    print("⏳ Waiting for login to complete...")

    max_wait = 180  # 3 minutes
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            res = requests.get(f"{API_BASE_URL}/cli_login/session/{session_id}/status", timeout=3)
            if res.status_code == 200:
                data = res.json()
                success = data.get("success", '0')
                if str(success) == '1':
                    uid = data.get("data", '')
                    if uid:
                        save_token(uid)
                        return
        except Exception as e:
            print("🌐 Error with checking login status. Retrying..." + str(e))
            pass
        time.sleep(1)

    print("❌ Login timed out. Please try again.")
    sys.exit(1)



def pull(project_key: str, force=False):
    if not CONFIG_PATH.exists():
        print("❌ Not logged in. Run `waveassist login` first.")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    uid = config.get("uid")
    if not uid:
        print("❌ No uid found.")
        return

    print("📥 Pulling latest project bundle from WaveAssist...")

    try:
        res = requests.get(
            f"{API_BASE_URL}/cli/project/{project_key}/pull_bundle/",
            headers={"Authorization": f"Bearer {uid}"},
            stream=True
        )
        if res.status_code != 200:
            print(f"❌ Failed to fetch bundle. Status: {res.status_code}")
            print(res.text)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = f"{tmpdir}/project.zip"
            with open(zip_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            print("✅ Downloaded and extracted bundle.")

            # Optional: Confirm before overwrite
            if not force:
                confirm = input(
                    "⚠️ This will fetch files from WaveAssist and replace any with the same name in this folder. Continue? (y/N): ")
                if confirm.lower() != "y":
                    print("❌ Aborted.")
                    return

            # Overwrite local files
            for item in Path(tmpdir).iterdir():
                if item.name == "project.zip":
                    continue
                dest = Path.cwd() / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy(item, dest)

        print("✅ Pull complete. Your local project is now up to date.")
    except Exception as e:
        print("❌ Pull failed. Error message: ", str(e))



def push(project_key: str = None, force=False):
    if not CONFIG_PATH.exists():
        print("❌ Not logged in. Run `waveassist login` first.")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    uid = config.get("uid")
    if not uid:
        print("❌ No token found in config.")
        return

    # Verify wa.json exists
    wa_config = Path("config.yaml")
    if not wa_config.exists():
        print("❌ Missing config.yaml in current directory.")
        return

    # Create zip bundle
    bundle_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name

    with zipfile.ZipFile(bundle_path, "w") as bundle:
        for root, _, files in os.walk("."):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), ".")
                if ".git" in rel_path or ".env" in rel_path:
                    continue
                bundle.write(os.path.join(root, file), rel_path)

    # Optional: Confirm before overwrite
    if not force:
        confirm = input(
            "⚠️ This will replace the code on WaveAssist with files listed in config.yml. Continue? (y/N): ")
        if confirm.lower() != "y":
            print("❌ Aborted.")
            return

    # Upload to backend
    print("📦 Uploading bundle...")
    with open(bundle_path, "rb") as f:
        res = requests.post(
            f"{API_BASE_URL}/cli/project/{project_key}/push_bundle/",
            headers={"Authorization": f"Bearer {uid}"},
            files={"bundle": ("bundle.zip", f, "application/zip")},
        )
    if res.ok:
        print("✅ Project pushed to WaveAssist.")
    else:
        print(f"❌ Failed to push. Status {res.status_code}")
        print(res.text)



