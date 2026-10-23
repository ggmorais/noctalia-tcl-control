import contextlib
import io
import unittest
from unittest.mock import patch

import probe


class ProbeTests(unittest.TestCase):
    def test_endpoint_restrictions(self):
        for url in ("http://pa.account.tcl.com", "https://evil.example",
                    "https://tcl.com.evil.example", "https://user@pa.account.tcl.com",
                    "https://pa.account.tcl.com:8443"):
            with self.subTest(url=url), self.assertRaises(probe.ProbeError):
                probe.trusted_url(url)
        self.assertEqual(probe.trusted_url(probe.LOGIN_URL), probe.LOGIN_URL)

    def test_discovery_has_no_write_calls_or_secret_output(self):
        responses = [
            {"status": 1, "token": "SECRET_AUTH", "user": {"username": "private-id"}},
            {"data": {"cloud_url": "https://cloud.tcljd.com", "device_url": "https://device.tcljd.com"}},
            {"data": {"saasToken": "SECRET_SESSION"}},
            {"data": [{"deviceId": "PRIVATE_DEVICE", "nickName": "AC split",
                       "isOnline": 1, "deviceType": "split", "secret": "PRIVATE_KEY"}]},
        ]
        with patch.object(probe, "post", side_effect=responses) as post:
            with contextlib.redirect_stdout(io.StringIO()):
                result = probe.discover("private-user", "private-password")
        self.assertEqual(result[0]["nome"], "AC split")
        self.assertEqual(result[0]["online"], 1)
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("SECRET", str(result))
        self.assertEqual([call.args[0] for call in post.call_args_list], [
            probe.LOGIN_URL, probe.CLOUD_URL,
            "https://cloud.tcljd.com/v3/auth/refresh_tokens",
            "https://device.tcljd.com/v3/user/get_things",
        ])
        self.assertNotEqual(post.call_args_list[0].args[1]["password"], "private-password")

    def test_failed_login_does_not_echo_response(self):
        with patch.object(probe, "post", return_value={"status": 0, "message": "SECRET"}):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(probe.ProbeError) as error:
                    probe.discover("user", "password")
        self.assertNotIn("SECRET", str(error.exception))


if __name__ == "__main__":
    unittest.main()
