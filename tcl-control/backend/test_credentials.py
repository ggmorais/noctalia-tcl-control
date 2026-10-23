import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from credentials import load_credentials
from probe import ProbeError


class CredentialsTests(unittest.TestCase):
    def test_json_quoted_password_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            password = ' quoted "password" \\ $literal # text '
            path.write_text("TCL_LOGIN=example@example.test\nTCL_PASSWORD=" + json.dumps(password) + "\n")
            path.chmod(0o600)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_credentials(path)[1], password)

    def test_rejects_symlinked_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_text("TCL_LOGIN=test\nTCL_PASSWORD=secret\n")
            target.chmod(0o600)
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(ProbeError):
                load_credentials(link)

    def test_literals_are_not_executed_or_expanded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TCL_LOGIN='example@example.test'\nTCL_PASSWORD='$(false)#literal'\n")
            path.chmod(0o600)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_credentials(path), ("example@example.test", "$(false)#literal"))

    def test_rejects_world_readable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TCL_LOGIN=test\nTCL_PASSWORD=secret\n")
            path.chmod(0o644)
            with self.assertRaises(ProbeError):
                load_credentials(path)


if __name__ == "__main__":
    unittest.main()
