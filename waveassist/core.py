import argparse
import json
import logging
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

from waveassist.constants import API_BASE_URL, DASHBOARD_URL

logger = logging.getLogger("waveassist")

CONFIG_PATH = Path.home() / ".waveassist" / "config.json"


def save_token(uid: str):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"uid": uid}, f)
    logger.info("Logged in and saved to ~/.waveassist/config.json")


def login():
    session_id = str(uuid.uuid4())
    login_url = f"{DASHBOARD_URL}/login?session_id={session_id}"
    logger.info("Opening browser for login...")
    webbrowser.open(login_url)

    logger.info("Waiting for login to complete...")

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
            logger.warning("Error checking login status. Retrying: %s", e)
        time.sleep(1)

    logger.error("Login timed out. Please try again.")
    sys.exit(1)



def pull(project_key: str, force=False):
    if not CONFIG_PATH.exists():
        logger.error("Not logged in. Run `waveassist login` first.")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    uid = config.get("uid")
    if not uid:
        logger.error("No uid found.")
        return

    logger.info("Pulling latest project bundle from WaveAssist...")

    try:
        res = requests.get(
            f"{API_BASE_URL}/cli/project/{project_key}/pull_bundle/",
            headers={"Authorization": f"Bearer {uid}"},
            stream=True
        )
        if res.status_code != 200:
            logger.error("Failed to fetch bundle. Status: %s", res.status_code)
            logger.error("%s", res.text)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = f"{tmpdir}/project.zip"
            with open(zip_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            logger.info("Downloaded and extracted bundle.")

            # Optional: Confirm before overwrite
            if not force:
                confirm = input(
                    "This will fetch files from WaveAssist and replace any with the same name in this folder. Continue? (y/N): ")
                if confirm.lower() != "y":
                    logger.info("Aborted.")
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

        logger.info("Pull complete. Your local project is now up to date.")
    except Exception as e:
        logger.error("Pull failed. Error message: %s", e)



def push(project_key: str = None, force=False):
    if not CONFIG_PATH.exists():
        logger.error("Not logged in. Run `waveassist login` first.")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    uid = config.get("uid")
    if not uid:
        logger.error("No token found in config.")
        return

    # Verify wa.json exists
    wa_config = Path("config.yaml")
    if not wa_config.exists():
        logger.error("Missing config.yaml in current directory.")
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
            "This will replace the code on WaveAssist with files listed in config.yml. Continue? (y/N): ")
        if confirm.lower() != "y":
            logger.info("Aborted.")
            return

    # Upload to backend
    logger.info("Uploading bundle...")
    with open(bundle_path, "rb") as f:
        res = requests.post(
            f"{API_BASE_URL}/cli/project/{project_key}/push_bundle/",
            headers={"Authorization": f"Bearer {uid}"},
            files={"bundle": ("bundle.zip", f, "application/zip")},
        )
    if res.ok:
        logger.info("Project pushed to WaveAssist.")
    else:
        logger.error("Failed to push. Status %s", res.status_code)
        logger.error("%s", res.text)



