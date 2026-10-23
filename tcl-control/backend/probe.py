"""Read-only TCL Home login/device discovery. Python standard library only.

Protocol reference: nemesa/ha-tcl-home-unofficial-integration (MIT),
commit fdba4d7a0b8213f4f68a74b4ce0f932343802b6b.
Never saves credentials, tokens, or raw API responses.
"""

import getpass
import hashlib
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings

LOGIN_URL = "https://pa.account.tcl.com/account/login?clientId=54148614"
CLOUD_URL = "https://prod-center.aws.tcljd.com/v3/global/cloud_url_get"
APP_ID = "wx6e1af3fa84fbe523"


class ProbeError(Exception):
    pass


def trusted_url(url):
    """Do not send account tokens to arbitrary discovery/redirect targets."""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host.endswith(".tcl.com") or host.endswith(".tcljd.com"))):
        raise ProbeError("Endpoint inesperado; interrompido para proteger sua conta.")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(url, payload, headers=None):
    request = urllib.request.Request(
        trusted_url(url), data=json.dumps(payload).encode(),
        headers={"User-Agent": "Android", "Content-Type": "application/json; charset=UTF-8",
                 **(headers or {})}, method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProbeError(f"Servidor retornou HTTP {exc.code}. Nenhuma resposta sensível foi exibida.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProbeError("Falha de conexão com a TCL. Verifique a internet e tente novamente.") from None
    except (ValueError, UnicodeError):
        raise ProbeError("Resposta inesperada da TCL (não JSON).") from None
    if not isinstance(data, dict):
        raise ProbeError("Formato de resposta inesperado da TCL.")
    return data


def field(data, snake, camel):
    return data.get(snake, data.get(camel))


def connect(username, password):
    """Return session context in memory only; never print this return value."""
    print("1/4 Autenticando na TCL…", flush=True)
    auth = post(LOGIN_URL, {
        "equipment": 2, "password": hashlib.md5(password.encode()).hexdigest(),
        "osType": 1, "username": username, "clientVersion": "4.8.1",
        "osVersion": "6.0", "deviceModel": "AndroidAndroid SDK built for x86",
        "captchaRule": 2, "channel": "app",
    }, {"th_platform": "android", "th_version": "4.8.1", "th_appbulid": "830"})
    if auth.get("status") != 1 or not auth.get("token"):
        raise ProbeError("Login não aceito. Confira a conta/senha; CAPTCHA ou mudança da API também podem impedir o acesso. Não repita muitas vezes.")
    user_id = auth["user"]["username"]
    print("2/4 Descobrindo a região da conta…", flush=True)
    cloud = post(CLOUD_URL, {"ssoId": user_id, "ssoToken": auth["token"]})["data"]
    base = trusted_url(cloud["cloud_url"]).rstrip("/")
    device_base = trusted_url(cloud["device_url"]).rstrip("/")
    print("3/4 Obtendo sessão temporária…", flush=True)
    session = post(base + "/v3/auth/refresh_tokens", {
        "userId": user_id, "ssoToken": auth["token"], "appId": APP_ID,
    })["data"]
    token = field(session, "saas_token", "saasToken")
    if not token:
        raise ProbeError("A TCL não retornou uma sessão válida.")
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(8)
    print("4/4 Consultando aparelhos (sem enviar comandos)…", flush=True)
    devices = post(device_base + "/v3/user/get_things", {}, {
        "platform": "android", "appversion": "5.4.1", "thomeversion": "4.8.1",
        "accesstoken": token, "accept-language": "en", "timestamp": timestamp,
        "nonce": nonce, "sign": hashlib.md5((timestamp + nonce + token).encode()).hexdigest(),
    }).get("data")
    if not isinstance(devices, list):
        raise ProbeError("A TCL não retornou a lista de aparelhos esperada.")
    return cloud, session, devices


def discover(username, password):
    _, _, devices = connect(username, password)
    # Explicit allowlist: no device IDs, account info, keys, or tokens.
    return [{
        "nome": field(d, "nick_name", "nickName") or field(d, "device_name", "deviceName"),
        "categoria": d.get("category"),
        "tipo": field(d, "device_type", "deviceType"),
        "plataforma": d.get("platform"),
        "online": field(d, "is_online", "isOnline"),
        "firmware": field(d, "firmware_version", "firmwareVersion"),
    } for d in devices]


def main():
    if not sys.stdin.isatty():
        print("Execute em um terminal interativo. Não passe sua senha por comando ou arquivo.")
        return 1
    try:
        print("Teste somente de leitura. Senha e tokens não serão salvos.")
        username = input("E-mail/usuário TCL Home: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Senha TCL Home (oculta): ")
        if not username or not password:
            raise ProbeError("Usuário e senha são necessários.")
        devices = discover(username, password)
        print("\nResultado (sem credenciais ou IDs):")
        print(json.dumps(devices, ensure_ascii=False, indent=2))
        print("\nConsulta concluída. Nenhum comando foi enviado ao ar.")
        return 0
    except ProbeError as exc:
        print(f"\nErro: {exc}", file=sys.stderr)
    except (KeyError, TypeError, ValueError):
        print("\nResposta incompatível com o protocolo esperado. Nenhum dado sensível foi exibido.", file=sys.stderr)
    except getpass.GetPassWarning:
        print("\nNão foi possível ocultar a senha. Use um terminal normal.", file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
