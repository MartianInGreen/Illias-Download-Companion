#!/usr/bin/env python3
"""Install the native messaging manifest for the current user."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import stat

HOST_NAME = "io.github.ilias_download_companion"
EXTENSION_ID = "ilias-download-companion@local"


def firefox_manifest_dir() -> Path:
    system = platform.system()
    if system == "Linux":
        return Path.home() / ".mozilla" / "native-messaging-hosts"
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Mozilla/NativeMessagingHosts"
    raise SystemExit("Automatic installation currently supports Linux and macOS only.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-dir", type=Path, default=firefox_manifest_dir())
    args = parser.parse_args()

    host = Path(__file__).resolve().with_name("host.py")
    host.chmod(host.stat().st_mode | stat.S_IXUSR)
    manifest = {
        "name": HOST_NAME,
        "description": "Runs PFERD for the active ILIAS course",
        "path": str(host),
        "type": "stdio",
        "allowed_extensions": [EXTENSION_ID],
    }
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    destination = args.manifest_dir / f"{HOST_NAME}.json"
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Installed native messaging manifest at {destination}")


if __name__ == "__main__":
    main()
