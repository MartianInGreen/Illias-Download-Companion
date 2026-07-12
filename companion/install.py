#!/usr/bin/env python3
"""Install and configure the Firefox native messaging companion."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import site
import stat
import subprocess
import sys
from typing import Callable
from urllib.parse import urlsplit

HOST_NAME = "io.github.ilias_download_companion"
EXTENSION_ID = "ilias-download-companion@local"


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ilias-download-companion"


def firefox_manifest_dir() -> Path:
    system = platform.system()
    if system == "Linux":
        return Path.home() / ".mozilla" / "native-messaging-hosts"
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Mozilla/NativeMessagingHosts"
    raise SystemExit("Automatic installation currently supports Linux and macOS only.")


def ask(
    prompt: str,
    default: str | None = None,
    *,
    validate: Callable[[str], bool] | None = None,
) -> str:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            value = default
        if value and (validate is None or validate(value)):
            return value
        print("Please enter a valid value.")


def confirm(prompt: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{marker}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def choose(prompt: str, choices: list[tuple[str, str]], default: int = 1) -> str:
    print(prompt)
    for index, (_, description) in enumerate(choices, start=1):
        print(f"  {index}. {description}")
    while True:
        value = input(f"Choose [{default}]: ").strip() or str(default)
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value) - 1][0]
        print(f"Enter a number from 1 to {len(choices)}.")


def https_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.path.rstrip("/")
    except ValueError:
        return False


def https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname)
    except ValueError:
        return False


def safe_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "-" for character in value.lower())
    return "-".join(filter(None, cleaned.split("-"))) or "ilias"


def write_credential(path: Path, username: str, password: str) -> None:
    if "\n" in username or "\n" in password or "\r" in username or "\r" in password:
        raise ValueError("Credentials cannot contain line breaks.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"username={username}\npassword={password}\n")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    path.chmod(0o600)


def configure_auth(profile_name: str, directory: Path) -> list[str]:
    method = choose(
        "Authentication method:",
        [
            ("credential", "Credential file (recommended; works immediately)"),
            ("keyring", "System keyring (password must be initialized in PFERD)"),
        ],
    )
    username = ask("ILIAS username")
    if method == "keyring":
        return ["--keyring", "--username", username]

    while True:
        password = getpass.getpass("ILIAS password: ")
        confirmation = getpass.getpass("Repeat password: ")
        if password and password == confirmation:
            break
        print("Passwords did not match or were empty. Please try again.")
    credential = directory / "credentials" / f"{safe_name(profile_name)}.txt"
    write_credential(credential, username, password)
    print(f"Created owner-only credential file: {credential}")
    return ["--credential-file", str(credential)]


def configure_profile(directory: Path, number: int) -> dict[str, object]:
    print(f"\nConfigure ILIAS profile {number}")
    print("-------------------------")
    name = ask("Profile name", f"ILIAS {number}")
    kind = choose(
        "ILIAS installation:",
        [("kit-ilias-web", "KIT ILIAS"), ("ilias-web", "Another ILIAS installation")],
    )
    default_origin = "https://ilias.studium.kit.edu" if kind == "kit-ilias-web" else None
    origin = ask("ILIAS origin (HTTPS, without a path)", default_origin, validate=https_origin).rstrip("/")
    output = ask("Course library directory", str(Path.home() / "Study" / safe_name(name)))
    conflict = choose(
        "When local and remote files conflict:",
        [
            ("no-delete", "Update files but keep local-only files (recommended)"),
            ("remote-first", "Make the local copy exactly follow ILIAS"),
            ("local-first", "Keep the local version when files differ"),
        ],
    )
    options = configure_auth(name, directory) + ["--on-conflict", conflict]
    profile: dict[str, object] = {
        "name": name,
        "origin": origin,
        "crawler": kind,
        "outputDir": str(Path(output).expanduser().resolve()),
        "options": options,
    }
    if kind == "ilias-web":
        profile["baseUrl"] = ask("ILIAS base URL", origin, validate=https_url).rstrip("/")
        client_id = ask("ILIAS client ID (enter '-' if none)", "-")
        if client_id != "-":
            profile["clientId"] = client_id
    return profile


def find_pferd() -> str:
    detected = shutil.which("pferd")
    if detected:
        print(f"Found PFERD: {detected}")
        return detected
    print("PFERD was not found on PATH.")
    if confirm("Install PFERD now with Python pip?", True):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "PFERD"],
            check=False,
        )
        candidates = [shutil.which("pferd"), str(Path(site.USER_BASE) / "bin" / "pferd")]
        detected = next((value for value in candidates if value and Path(value).is_file()), None)
        if result.returncode == 0 and detected:
            print(f"Installed PFERD: {detected}")
            return detected
        print("Automatic PFERD installation did not succeed.")
    path = ask(
        "Absolute path to the PFERD executable",
        validate=lambda value: Path(value).expanduser().is_file(),
    )
    return str(Path(path).expanduser().resolve())


def install_manifest(destination_dir: Path) -> Path:
    host = Path(__file__).resolve().with_name("host.py")
    host.chmod(host.stat().st_mode | stat.S_IXUSR)
    manifest = {
        "name": HOST_NAME,
        "description": "Runs PFERD for the active ILIAS course",
        "path": str(host),
        "type": "stdio",
        "allowed_extensions": [EXTENSION_ID],
    }
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{HOST_NAME}.json"
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination


def verify_pferd(executable: str) -> None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"Could not run PFERD: {error}") from error
    if result.returncode != 0:
        raise SystemExit(f"PFERD verification failed: {result.stderr.strip()}")
    print(result.stdout.strip())


def run_wizard(manifest_dir: Path) -> None:
    print("ILIAS Download Companion setup")
    print("================================\n")
    executable = find_pferd()
    verify_pferd(executable)

    directory = config_dir()
    config_path = directory / "config.json"
    if config_path.exists() and not confirm(f"Replace existing configuration at {config_path}?", False):
        manifest = install_manifest(manifest_dir)
        print(f"\nKept existing configuration.\nInstalled native manifest: {manifest}")
        return

    profiles = []
    while True:
        profiles.append(configure_profile(directory, len(profiles) + 1))
        if not confirm("Add another ILIAS installation?", False):
            break

    timeout = int(ask(
        "Maximum update duration in seconds",
        "3600",
        validate=lambda value: value.isdigit() and int(value) > 0,
    ))
    config = {"pferd": executable, "timeoutSeconds": timeout, "profiles": profiles}
    directory.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    config_path.chmod(0o600)
    manifest = install_manifest(manifest_dir)

    print("\nSetup complete")
    print("--------------")
    print(f"Configuration: {config_path}")
    print(f"Native manifest: {manifest}")
    print("Credential files are readable only by your user.")
    print("\nLoad extension/manifest.json from about:debugging in Firefox, then open")
    print("an ILIAS course and click the extension. Restart Firefox if it was open")
    print("while this installer ran.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, default=firefox_manifest_dir())
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="install only the native messaging manifest without prompting",
    )
    args = parser.parse_args()
    if args.manifest_only:
        print(f"Installed native messaging manifest at {install_manifest(args.manifest_dir)}")
    else:
        run_wizard(args.manifest_dir)


if __name__ == "__main__":
    main()
