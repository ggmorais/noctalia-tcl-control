"""Read AWS IoT reported state using a temporary TCL Home session. No writes."""

import base64
from contextlib import closing
import getpass
import json
import re
import sys
import warnings

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from probe import ProbeError, connect, field

STATE_KEYS = (
    "powerSwitch", "targetTemperature", "currentTemperature", "workMode",
    "windSpeed", "windSpeedAutoSwitch", "windSpeed7Gear", "verticalSwitch",
    "horizontalSwitch", "screen", "ECO", "turbo", "silenceSwitch", "sleep",
)


def safe_state(state):
    """Only export known scalar controls, never arbitrary metadata or identifiers."""
    return {key: state[key] for key in STATE_KEYS
            if key in state and type(state[key]) in (int, float, bool)}


def summarize_shadow(shadow):
    state = shadow.get("state", {})
    reported = state.get("reported", {})
    capabilities = reported.get("capabilities", [])
    if not isinstance(capabilities, list) or not all(type(c) is int for c in capabilities):
        capabilities = []
    return {
        "estado_reportado": safe_state(reported),
        "alteracoes_pendentes": safe_state(state.get("delta", {})),
        "capacidades_numericas": capabilities,
        "campos_de_controle_disponiveis": [key for key in STATE_KEYS if key in reported],
        "atualizado_em_unix": shadow.get("timestamp"),
    }


def open_iot(cloud, session, sdk=None):
    region = cloud["cloud_region"]
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
        raise ProbeError("Região AWS inesperada.")
    cognito_token = field(session, "cognito_token", "cognitoToken")
    if not cognito_token:
        raise ProbeError("A sessão TCL não retornou o token necessário para consultar o estado.")
    # Decode only to extract the identity ID. AWS validates the actual token.
    encoded = cognito_token.split(".")[1]
    identity = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))["sub"]
    if not isinstance(identity, str) or not identity.startswith(region + ":"):
        raise ProbeError("Identidade AWS inesperada.")
    sdk = sdk or boto3.session.Session()
    common = {"connect_timeout": 10, "read_timeout": 20,
              "retries": {"total_max_attempts": 1}}
    with closing(sdk.client("cognito-identity", region_name=region,
                           config=Config(signature_version=UNSIGNED, **common))) as cognito:
        credentials = cognito.get_credentials_for_identity(
            IdentityId=identity,
            Logins={"cognito-identity.amazonaws.com": cognito_token},
        )["Credentials"]
    # Same SDK endpoint resolution as the reference Home Assistant integration.
    return sdk.client("iot-data", region_name=region,
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretKey"],
                    aws_session_token=credentials["SessionToken"],
                      config=Config(**common))


def read_states(cloud, session, devices, sdk=None):
    with closing(open_iot(cloud, session, sdk)) as iot:
        result = []
        for device in devices:
            if device.get("category") != "AC":
                continue
            device_id = field(device, "device_id", "deviceId")
            if not device_id:
                raise ProbeError("Aparelho sem identificador na resposta TCL.")
            response = iot.get_thing_shadow(thingName=device_id)
            with response["payload"] as stream:
                shadow = json.loads(stream.read())
            result.append({"nome": field(device, "device_name", "deviceName"),
                           **summarize_shadow(shadow)})
        return result


def main():
    from credentials import load_credentials

    use_env = "--env" in sys.argv[1:]
    if not use_env and not sys.stdin.isatty():
        print("Execute em um terminal interativo.", file=sys.stderr)
        return 1
    try:
        print("Consulta de estado: não envia comandos e não salva novos dados de autenticação.")
        if use_env:
            username, password = load_credentials()
        else:
            username = input("E-mail/usuário TCL Home: ").strip()
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("Senha TCL Home (oculta): ")
        if not username or not password:
            raise ProbeError("Usuário e senha são necessários.")
        cloud, session, devices = connect(username, password)
        print("5/5 Consultando o estado reportado na AWS IoT…", flush=True)
        states = read_states(cloud, session, devices)
        print("\nResultado (sem credenciais ou IDs):")
        print(json.dumps(states, ensure_ascii=False, indent=2))
        print("\nNenhum comando foi enviado. Valores ainda brutos, sem conversão de temperatura/modo.")
        return 0
    except ProbeError as exc:
        print(f"\nErro: {exc}", file=sys.stderr)
    except ClientError as exc:
        # Do not print AWS messages: they can contain account/device identifiers.
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", "?")
        print(f"\nConsulta AWS recusada (HTTP {status}). Nenhuma resposta sensível foi exibida.", file=sys.stderr)
    except BotoCoreError:
        print("\nFalha de comunicação/configuração AWS. Nenhum dado sensível foi exibido.", file=sys.stderr)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        print("\nResposta incompatível com o formato esperado. Nenhum dado sensível foi exibido.", file=sys.stderr)
    except getpass.GetPassWarning:
        print("\nNão foi possível ocultar a senha. Use um terminal normal.", file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
