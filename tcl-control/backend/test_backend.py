import json
import unittest
from unittest.mock import MagicMock, patch

from backend import Controller, desired_state, safe_handle
from probe import ProbeError


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.state = {"powerSwitch": 1, "targetTemperature": 22, "workMode": 3,
                      "windSpeed": 3, "turbo": 0, "silenceSwitch": 0, "screen": 1}

    def test_allowlist(self):
        self.assertEqual(desired_state("temperature", "23", self.state), {"targetTemperature": 23})
        self.assertEqual(desired_state("power", "off", self.state), {"powerSwitch": 0})
        self.assertEqual(desired_state("mode", "cool", self.state), {"workMode": 1})
        for action, value in (("temperature", "50"), ("temperature", "15"),
                              ("temperature", "NaN"), ("raw", "anything"),
                              ("power", "toggle"), ("fan", "100")):
            with self.subTest(action=action, value=value), self.assertRaises(ProbeError):
                desired_state(action, value, self.state)

    def test_no_implicit_power_change(self):
        for action, value in (("temperature", "22"), ("mode", "cool"), ("fan", "4")):
            self.assertNotIn("powerSwitch", desired_state(action, value, self.state))

    def test_control_requires_reported_support(self):
        with self.assertRaises(ProbeError):
            desired_state("screen", "on", {})

    def test_read_does_not_publish(self):
        controller = Controller()
        with patch.object(controller, "read", return_value={"ok": True}):
            controller.iot = MagicMock()
            self.assertTrue(controller.handle({"action": "status"})["ok"])
            controller.iot.publish.assert_not_called()

    def test_write_only_explicit_desired_fields(self):
        controller = Controller()
        controller.device = {"isOnline": "1"}
        controller.device_id = "private-device"
        controller.iot = MagicMock()
        with patch.object(controller, "read", return_value={"ok": True, "state": self.state, "pending": {}}):
            result = controller.handle({"action": "temperature", "value": "23"})
        payload = json.loads(controller.iot.publish.call_args.kwargs["payload"])
        self.assertEqual(payload["state"]["desired"], {"targetTemperature": 23})
        self.assertEqual(result["state"]["targetTemperature"], 22)
        self.assertEqual(result["pending"], {"targetTemperature": 23})

    def test_errors_never_leak_raw_exception(self):
        controller = MagicMock()
        controller.handle.side_effect = ValueError("SECRET")
        self.assertNotIn("SECRET", str(safe_handle(controller, {})))


if __name__ == "__main__":
    unittest.main()
