#!/usr/bin/env python3
"""Firefox native messaging host that invokes PFERD for an allowlisted URL."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, BinaryIO
from urllib.parse import urlsplit

HOST_NAME = "io.github.ilias_download_companion"
MAX_MESSAGE_SIZE = 1024 * 1024
ALLOWED_CRAWLERS = {"ilias-web", "kit-ilias-web"}
ALLOWED_OPTIONS = {
    "--client-id",
    "--credential-file",
    "--forums",
    "--http-timeout",
    "--keyring",
    "--links",
    "--no-forums",
    "--no-keyring",
    "--no-videos",
    "--on-conflict",
    "--redownload",
    "--task-delay",
    "--tasks",
    "--username",
    "--videos",
}


class CompanionError(Exception):
    pass


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    raw_length = stream.read(4)
    if not raw_length:
        return None
    if len(raw_length) != 4:
        raise CompanionError("Invalid native message header.")
    length = struct.unpack("=I", raw_length)[0]
    if length > MAX_MESSAGE_SIZE:
        raise CompanionError("Native message is too large.")
    payload = stream.read(length)
    if len(payload) != length:
        raise CompanionError("Incomplete native message.")
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict):
        raise CompanionError("Native message must be an object.")
    return message


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=True).encode("utf-8")
    stream.write(struct.pack("=I", len(payload)))
    stream.write(payload)
    stream.flush()


def config_path() -> Path:
    override = os.environ.get("ILIAS_COMPANION_CONFIG")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ilias-download-companion" / "config.json"


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CompanionError(f"Config not found: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise CompanionError(f"Could not read config: {error}") from error
    if not isinstance(config, dict) or not isinstance(config.get("profiles"), list):
        raise CompanionError("Config must contain a profiles array.")
    return config


def normalized_origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise CompanionError("Only HTTPS ILIAS URLs without embedded credentials are allowed.")
    default_port = parsed.port in (None, 443)
    return f"https://{parsed.hostname.lower()}{'' if default_port else f':{parsed.port}'}"


def select_profile(config: dict[str, Any], url: str) -> dict[str, Any]:
    origin = normalized_origin(url)
    for profile in config["profiles"]:
        if isinstance(profile, dict) and profile.get("origin", "").rstrip("/").lower() == origin:
            return profile
    raise CompanionError(f"No profile allows {origin}.")


def build_command(config: dict[str, Any], profile: dict[str, Any], url: str) -> list[str]:
    name = profile.get("name")
    crawler = profile.get("crawler")
    output_dir = profile.get("outputDir")
    if not isinstance(name, str) or not name.strip():
        raise CompanionError("Every profile needs a non-empty name.")
    if crawler not in ALLOWED_CRAWLERS:
        raise CompanionError(f"Profile {name!r} has an unsupported crawler.")
    if not isinstance(output_dir, str) or not output_dir:
        raise CompanionError(f"Profile {name!r} needs outputDir.")

    executable = config.get("pferd", "pferd")
    if not isinstance(executable, str) or not executable:
        raise CompanionError("pferd must be an executable path.")
    command = [executable, "--no-status", crawler]

    if crawler == "ilias-web":
        base_url = profile.get("baseUrl", profile.get("origin"))
        if not isinstance(base_url, str) or normalized_origin(base_url) != normalized_origin(url):
            raise CompanionError(f"Profile {name!r} has an invalid baseUrl.")
        command.extend(["--base-url", base_url.rstrip("/")])
        client_id = profile.get("clientId")
        if client_id:
            command.extend(["--client-id", str(client_id)])

    options = profile.get("options", [])
    if not isinstance(options, list) or not all(isinstance(item, str) for item in options):
        raise CompanionError(f"Profile {name!r} options must be an array of strings.")
    for item in options:
        if item.startswith("-") and item.split("=", 1)[0] not in ALLOWED_OPTIONS:
            raise CompanionError(f"PFERD option {item!r} is not allowed.")
    command.extend(options)
    command.extend([url, str(Path(output_dir).expanduser())])
    return command


def update(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("action") != "update" or not isinstance(message.get("url"), str):
        raise CompanionError("Expected an update action with a URL.")
    config = load_config(config_path())
    profile = select_profile(config, message["url"])
    command = build_command(config, profile, message["url"])
    timeout = config.get("timeoutSeconds", 3600)
    if not isinstance(timeout, int) or timeout < 1:
        raise CompanionError("timeoutSeconds must be a positive integer.")

    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise CompanionError(f"PFERD executable not found: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise CompanionError(f"PFERD timed out after {timeout} seconds.") from error

    output = result.stdout.strip()
    summary = output[-4000:]
    if result.returncode != 0:
        raise CompanionError(f"PFERD exited with code {result.returncode}.\n{summary}")
    return {"ok": True, "profile": profile["name"], "summary": summary}


def main() -> int:
    try:
        message = read_message(sys.stdin.buffer)
        if message is None:
            return 0
        response = update(message)
    except (CompanionError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        response = {"ok": False, "error": str(error)}
    write_message(sys.stdout.buffer, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
