import argparse
import json
import platform
from waveassist.core import login, push, pull  # You can add deploy, status later
from waveassist._config import VERSION

def main():
    parser = argparse.ArgumentParser(
        prog="waveassist",
        description="WaveAssist CLI — Run & manage hosted workflows",
        add_help=True
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # login
    subparsers.add_parser("login", help="Authenticate via browser and store token")

    # version
    subparsers.add_parser("version", help="Show CLI version info")

    # push
    parser_push = subparsers.add_parser("push", help="Push local Python code to WaveAssist (code-only)")
    parser_push.add_argument("project_key", help="The ID of the project to push")
    parser_push.add_argument("--force", action="store_true", help="Skip confirmation before pushing")

    # pull
    parser_pull = subparsers.add_parser("pull", help="Pull Python code from WaveAssist (code-only)")
    parser_pull.add_argument("project_key", help="The ID of the project to pull")
    parser_pull.add_argument("--force", action="store_true", help="Skip confirmation before overwriting files")

    args = parser.parse_args()

    if args.command == "login":
        login()

    elif args.command == "push":
        push(args.project_key, force=args.force)

    elif args.command == "pull":
        pull(args.project_key, force=args.force)

    elif args.command == "version":
        print("🔷 WaveAssist CLI")
        print(f"   Version     : v{VERSION}")
        print("   Python      :", platform.python_version())


if __name__ == "__main__":
    main()
