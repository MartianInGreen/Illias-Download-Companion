import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from companion.install import https_origin, install_manifest, safe_name, write_credential


class InstallerTests(unittest.TestCase):
    def test_writes_owner_only_credential_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials" / "university.txt"
            write_credential(path, "student", "secret")
            self.assertEqual(path.read_text(), "username=student\npassword=secret\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_rejects_credential_line_breaks(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                write_credential(Path(directory) / "credentials.txt", "student", "bad\npassword")

    def test_installs_native_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = install_manifest(Path(directory))
            manifest = json.loads(destination.read_text())
            self.assertEqual(manifest["name"], "io.github.ilias_download_companion")
            self.assertTrue(Path(manifest["path"]).is_absolute())
            self.assertEqual(manifest["allowed_extensions"], ["ilias-download-companion@local"])

    def test_validates_origin_without_path(self):
        self.assertTrue(https_origin("https://ilias.example.edu"))
        self.assertFalse(https_origin("http://ilias.example.edu"))
        self.assertFalse(https_origin("https://ilias.example.edu/login.php"))

    def test_safe_name(self):
        self.assertEqual(safe_name("Example University!"), "example-university")


if __name__ == "__main__":
    unittest.main()
