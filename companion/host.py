#!/usr/bin/env python3
"""Firefox native messaging host that invokes PFERD for an allowlisted URL."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import tomllib
from typing import Any, BinaryIO
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit, urlunsplit

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


def output_root(profile: dict[str, Any]) -> Path:
    output_dir = profile.get("outputDir")
    if not isinstance(output_dir, str) or not output_dir:
        raise CompanionError(f"Profile {profile.get('name', '<unnamed>')!r} needs outputDir.")
    return Path(output_dir).expanduser()


def course_key(url: str) -> str:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    for field in ("target", "ref_id", "obj_id"):
        if query.get(field):
            return f"{normalized_origin(url)}:{field}:{query[field][0]}"
    canonical = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    return canonical


def course_directory(root: Path, title: str, key: str) -> Path:
    clean_title = re.sub(r"\s+[|:-]\s+ILIAS.*$", "", title, flags=re.IGNORECASE)
    slug = re.sub(r"[^A-Za-z0-9._ -]+", "", clean_title).strip(" ._-")
    slug = re.sub(r"\s+", "-", slug)[:70] or "course"
    suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return root / f"{slug}-{suffix}"


def registry_path(root: Path) -> Path:
    return root / "courses.toml"


def load_registry(root: Path) -> list[dict[str, Any]]:
    path = registry_path(root)
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CompanionError(f"Could not read course registry {path}: {error}") from error
    courses = data.get("courses", [])
    if not isinstance(courses, list) or not all(isinstance(item, dict) for item in courses):
        raise CompanionError(f"Course registry {path} has an invalid courses list.")
    return courses


def toml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=True)


def save_registry(root: Path, courses: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = ["# Managed by ILIAS Download Companion.\n"]
    fields = (
        "id", "title", "url", "directory", "added", "last_attempt",
        "last_crawled", "file_count", "last_status", "last_error",
    )
    for course in sorted(courses, key=lambda item: str(item.get("title", "")).lower()):
        lines.append("\n[[courses]]\n")
        for field in fields:
            if field not in course:
                continue
            value = course[field]
            if field == "file_count":
                lines.append(f"{field} = {int(value)}\n")
            else:
                lines.append(f"{field} = {toml_string(value)}\n")
    path = registry_path(root)
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text("".join(lines), encoding="utf-8")
    temporary.replace(path)


def find_course(courses: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next((item for item in courses if item.get("id") == key), None)


def public_course(course: dict[str, Any] | None) -> dict[str, Any] | None:
    if course is None:
        return None
    return {field: course.get(field) for field in (
        "title", "directory", "added", "last_attempt", "last_crawled",
        "file_count", "last_status", "last_error",
    ) if field in course}


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def pferd_failure(returncode: int, output: str) -> str:
    summary = output[-4000:]
    auth_markers = (
        "GetPassWarning",
        "fallback_getpass",
        "Password input may be echoed",
        "EOFError",
    )
    if any(marker in output for marker in auth_markers):
        return (
            "PFERD needs an interactive password, which the Firefox companion "
            "cannot provide. Run the same PFERD command once in a terminal with "
            "--keyring to save the password, or configure --credential-file. "
            "Then verify that command runs a second time without prompting.\n\n"
            f"PFERD output:\n{summary}"
        )
    if returncode < 0:
        return f"PFERD was terminated by signal {-returncode}.\n{summary}"
    return f"PFERD exited with code {returncode}.\n{summary}"


def build_command(
    config: dict[str, Any],
    profile: dict[str, Any],
    url: str,
    destination: Path | None = None,
) -> list[str]:
    name = profile.get("name")
    crawler = profile.get("crawler")
    if not isinstance(name, str) or not name.strip():
        raise CompanionError("Every profile needs a non-empty name.")
    if crawler not in ALLOWED_CRAWLERS:
        raise CompanionError(f"Profile {name!r} has an unsupported crawler.")
    root = output_root(profile)

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
    command.extend([url, str(destination or root)])
    return command


def terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        if process.poll() is not None:
            process.wait()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
    finally:
        if process.stdout is not None:
            process.stdout.close()


def run_pferd(command: list[str], timeout: int) -> tuple[int, str]:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise CompanionError(f"PFERD executable not found: {command[0]}") from error
    except OSError as error:
        raise CompanionError(f"Could not start PFERD: {error}") from error
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        terminate_process(process)
        raise CompanionError(f"PFERD timed out after {timeout} seconds and was stopped.") from error
    except BaseException:
        terminate_process(process)
        raise
    process.wait()
    return process.returncode, output.strip()


def request_context(message: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path, str]:
    if not isinstance(message.get("url"), str):
        raise CompanionError("Expected an ILIAS URL.")
    config = load_config(config_path())
    profile = select_profile(config, message["url"])
    root = output_root(profile)
    return config, profile, root, course_key(message["url"])


def status(message: dict[str, Any]) -> dict[str, Any]:
    _, profile, root, key = request_context(message)
    course = find_course(load_registry(root), key)
    return {"ok": True, "profile": profile["name"], "course": public_course(course)}


def update(message: dict[str, Any]) -> dict[str, Any]:
    config, profile, root, key = request_context(message)
    title = message.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "ILIAS course"
    courses = load_registry(root)
    course = find_course(courses, key)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if course is None:
        destination = course_directory(root, title, key)
        course = {
            "id": key,
            "title": title.strip(),
            "url": message["url"],
            "directory": str(destination),
            "added": now,
            "file_count": 0,
        }
        courses.append(course)
    else:
        destination = Path(str(course["directory"])).expanduser()
        course["title"] = title.strip()
        course["url"] = message["url"]
    course["last_attempt"] = now
    course["last_status"] = "running"
    course.pop("last_error", None)
    save_registry(root, courses)

    try:
        command = build_command(config, profile, message["url"], destination)
        timeout = config.get("timeoutSeconds", 3600)
        if not isinstance(timeout, int) or timeout < 1:
            raise CompanionError("timeoutSeconds must be a positive integer.")
        returncode, output = run_pferd(command, timeout)
    except CompanionError as error:
        course["last_status"] = "failed"
        course["last_error"] = str(error)
        save_registry(root, courses)
        raise
    summary = output[-4000:]
    if returncode != 0:
        course["last_status"] = "failed"
        course["last_error"] = pferd_failure(returncode, output)
        save_registry(root, courses)
        raise CompanionError(course["last_error"])
    course["last_status"] = "success"
    course["last_crawled"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    course["file_count"] = count_files(destination)
    save_registry(root, courses)
    return {
        "ok": True,
        "profile": profile["name"],
        "summary": summary,
        "course": public_course(course),
    }


def main() -> int:
    try:
        message = read_message(sys.stdin.buffer)
        if message is None:
            return 0
        if message.get("action") == "update":
            response = update(message)
        elif message.get("action") == "status":
            response = status(message)
        else:
            raise CompanionError("Expected an update or status action.")
    except (CompanionError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        response = {"ok": False, "error": str(error)}
    write_message(sys.stdout.buffer, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
