import io
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from companion.host import CompanionError, build_command, read_message, select_profile, write_message


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


if __name__ == "__main__":
    unittest.main()
