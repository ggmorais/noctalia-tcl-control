import base64
import io
import json
import unittest
import datetime
from unittest.mock import MagicMock

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.stub import Stubber

from probe import ProbeError
from status import read_states, summarize_shadow


class StatusTests(unittest.TestCase):
    def test_real_sdk_clients_without_context_manager(self):
        # Regression: MagicMock accepted `with client`, but real boto clients do not.
        session = boto3.session.Session()
        cognito = session.client("cognito-identity", region_name="eu-west-1", config=Config(signature_version=UNSIGNED))
        iot = session.client("iot-data", region_name="eu-west-1", aws_access_key_id="A" * 20,
                             aws_secret_access_key="S" * 40, aws_session_token="T" * 32)
        identity = "eu-west-1:00000000-0000-0000-0000-000000000001"
        encoded = base64.urlsafe_b64encode(json.dumps({"sub": identity}).encode()).decode().rstrip("=")
        token = f"header.{encoded}.signature"
        with Stubber(cognito) as auth_stub, Stubber(iot) as iot_stub:
            auth_stub.add_response("get_credentials_for_identity", {"Credentials": {
                "AccessKeyId": "A" * 20, "SecretKey": "S" * 40, "SessionToken": "T" * 32,
                "Expiration": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            }}, {"IdentityId": identity, "Logins": {"cognito-identity.amazonaws.com": token}})
            iot_stub.add_response("get_thing_shadow", {"payload": io.BytesIO(b'{"state":{"reported":{"powerSwitch":1}}}')}, {"thingName": "private-id"})
            sdk = MagicMock()
            sdk.client.side_effect = [cognito, iot]
            result = read_states({"cloud_region": "eu-west-1"}, {"cognitoToken": token},
                                 [{"category": "AC", "deviceId": "private-id"}], sdk)
            self.assertEqual(result[0]["estado_reportado"], {"powerSwitch": 1})
            auth_stub.assert_no_pending_responses()
            iot_stub.assert_no_pending_responses()

    def test_summary_excludes_secrets_and_separates_pending(self):
        result = summarize_shadow({"state": {
            "reported": {"powerSwitch": 1, "targetTemperature": 240,
                         "deviceId": "SECRET", "capabilities": [1, 2],
                         "screen": {"token": "SECRET"}},
            "delta": {"targetTemperature": 250, "token": "SECRET"},
        }})
        self.assertEqual(result["estado_reportado"]["targetTemperature"], 240)
        self.assertEqual(result["alteracoes_pendentes"], {"targetTemperature": 250})
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("screen", result["estado_reportado"])

    def test_only_reads_shadow(self):
        sdk = MagicMock()
        cognito = MagicMock()
        iot = MagicMock()
        sdk.client.side_effect = [cognito, iot]
        cognito.__enter__.return_value = cognito
        iot.__enter__.return_value = iot
        cognito.get_credentials_for_identity.return_value = {"Credentials": {
            "AccessKeyId": "KEY", "SecretKey": "SECRET", "SessionToken": "TOKEN"}}
        iot.get_thing_shadow.return_value = {"payload": io.BytesIO(
            b'{"state":{"reported":{"powerSwitch":1}}}')}
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "eu-west-1:identity"}).encode()).decode().rstrip("=")
        result = read_states({"cloud_region": "eu-west-1"},
                             {"cognitoToken": f"header.{payload}.signature"},
                             [{"category": "AC", "deviceId": "private-id", "deviceName": "Split AC"}], sdk)
        self.assertEqual(result[0]["estado_reportado"], {"powerSwitch": 1})
        iot.get_thing_shadow.assert_called_once_with(thingName="private-id")
        iot.publish.assert_not_called()
        iot.update_thing_shadow.assert_not_called()
        self.assertNotIn("private-id", str(result))

    def test_rejects_invalid_region(self):
        with self.assertRaises(ProbeError):
            read_states({"cloud_region": "evil.example"}, {}, [], MagicMock())


if __name__ == "__main__":
    unittest.main()
