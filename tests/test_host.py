import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from companion.host import (
    CompanionError,
    build_command,
    course_directory,
    course_key,
    load_registry,
    read_message,
    run_pferd,
    save_registry,
    select_profile,
    write_message,
)


class MessageTests(unittest.TestCase):
    def test_round_trip(self):
        stream = io.BytesIO()
        write_message(stream, {"action": "update", "url": "https://example.edu/course"})
        stream.seek(0)
        self.assertEqual(read_message(stream)["action"], "update")

    def test_rejects_oversized_message(self):
        with self.assertRaises(CompanionError):
            read_message(io.BytesIO(struct.pack("=I", 1024 * 1024 + 1)))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "name": "University",
            "origin": "https://ilias.example.edu",
            "crawler": "ilias-web",
            "baseUrl": "https://ilias.example.edu/",
            "clientId": "university",
            "outputDir": "~/study",
            "options": ["--keyring", "--username", "student"],
        }

    def test_builds_generic_ilias_command(self):
        command = build_command({"pferd": "/usr/bin/pferd"}, self.profile, "https://ilias.example.edu/goto.php?ref_id=42")
        self.assertEqual(command[0:3], ["/usr/bin/pferd", "--no-status", "ilias-web"])
        self.assertIn("--base-url", command)
        self.assertEqual(command[-2], "https://ilias.example.edu/goto.php?ref_id=42")
        self.assertEqual(command[-1], str(Path("~/study").expanduser()))

    def test_matches_exact_origin_only(self):
        config = {"profiles": [self.profile]}
        self.assertIs(select_profile(config, "https://ilias.example.edu/course"), self.profile)
        with self.assertRaises(CompanionError):
            select_profile(config, "https://evil.example/course")

    def test_rejects_unapproved_options(self):
        self.profile["options"] = ["--config", "/tmp/other"]
        with self.assertRaises(CompanionError):
            build_command({}, self.profile, "https://ilias.example.edu/course")

    def test_rejects_http(self):
        with self.assertRaises(CompanionError):
            select_profile({"profiles": [self.profile]}, "http://ilias.example.edu/course")

    def test_course_key_uses_stable_ilias_target(self):
        first = course_key("https://ilias.example.edu/goto.php?target=crs_42&foo=one")
        second = course_key("https://ilias.example.edu/goto.php?foo=two&target=crs_42")
        self.assertEqual(first, second)

    def test_course_directory_is_safe_and_stable(self):
        root = Path("/tmp/courses")
        first = course_directory(root, "Math / ILIAS", "course-42")
        second = course_directory(root, "Math / ILIAS", "course-42")
        self.assertEqual(first, second)
        self.assertEqual(first.parent, root)
        self.assertNotIn("/", first.name)


class RegistryTests(unittest.TestCase):
    def test_registry_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            courses = [{
                "id": "course:42",
                "title": "Math & Logic",
                "url": "https://example.edu/course?id=42",
                "directory": str(root / "math"),
                "added": "2026-07-12T10:00:00+00:00",
                "last_crawled": "2026-07-12T10:05:00+00:00",
                "file_count": 17,
                "last_status": "success",
            }]
            save_registry(root, courses)
            self.assertEqual(load_registry(root), courses)
            self.assertIn("[[courses]]", (root / "courses.toml").read_text())


class ProcessTests(unittest.TestCase):
    def test_timeout_terminates_and_reaps_process(self):
        with self.assertRaisesRegex(CompanionError, "was stopped"):
            run_pferd([sys.executable, "-c", "import time; time.sleep(30)"], 1)

    def test_nonzero_process_is_reaped(self):
        code, output = run_pferd(
            [sys.executable, "-c", "print('failed'); raise SystemExit(7)"],
            5,
        )
        self.assertEqual(code, 7)
        self.assertEqual(output, "failed")


if __name__ == "__main__":
    unittest.main()
