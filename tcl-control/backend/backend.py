"""Noctalia companion. Credentials stay in memory; commands use a private socket."""

import contextlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import time

from botocore.exceptions import BotoCoreError, ClientError

from credentials import load_credentials
from probe import ProbeError, connect, field
from status import open_iot, summarize_shadow

MODES = {"auto": 0, "cool": 1, "dry": 2, "fan": 3, "heat": 4}


def socket_path():
    root = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    folder = Path(root) / "tcl-control"
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.stat().st_uid != os.getuid() or folder.stat().st_mode & 0o077:
        raise ProbeError("Diretório de comunicação sem proteção adequada.")
    return folder / "backend.sock"


def desired_state(action, value, reported):
    """Strict command allowlist for this split. Does not implicitly switch power on."""
    if action == "power" and value in ("on", "off"):
        result = {"powerSwitch": int(value == "on")}
    elif action == "temperature" and value.isdigit() and 16 <= int(value) <= 30:
        result = {"targetTemperature": int(value)}
    elif action == "mode" and value in MODES:
        result = {"workMode": MODES[value]}
    elif action == "fan" and value in ("0", "2", "3", "4", "5", "6"):
        result = {"windSpeed": int(value)}
        # Normal fan selection disables special fan overrides, as in upstream.
        for key in ("turbo", "silenceSwitch"):
            if key in reported:
                result[key] = 0
    elif action == "screen" and value in ("on", "off"):
        result = {"screen": int(value == "on")}
    else:
        raise ProbeError("Comando ou valor não permitido.")
    if any(key not in reported for key in result):
        raise ProbeError("O aparelho não reportou suporte a esse controle.")
    return result


class Controller:
    def __init__(self):
        self.iot = None
        self.expires = 0
        self.device = None
        self.pending = {}

    def ensure_session(self):
        if self.iot is not None and time.monotonic() < self.expires:
            return
        self.close()
        with contextlib.redirect_stdout(io.StringIO()):
            cloud, session, devices = connect(*load_credentials())
        devices = [d for d in devices if d.get("category") == "AC"]
        if len(devices) != 1:
            raise ProbeError("Esperado exatamente um ar-condicionado na conta.")
        self.device = devices[0]
        self.device_id = field(self.device, "device_id", "deviceId")
        if not self.device_id:
            raise ProbeError("Identificador do aparelho ausente.")
        self.iot = open_iot(cloud, session)
        # Renew before the typical AWS temporary credential expiration.
        self.expires = time.monotonic() + 600

    def close(self):
        if self.iot is not None:
            self.iot.close()
        self.iot = None

    def read(self):
        self.ensure_session()
        response = self.iot.get_thing_shadow(thingName=self.device_id)
        with response["payload"] as stream:
            shadow = json.loads(stream.read())
        state = summarize_shadow(shadow)
        reported = state["estado_reportado"]
        self.pending = {k: v for k, v in self.pending.items() if reported.get(k) != v}
        return {"ok": True, "state": reported,
                "pending": {**state["alteracoes_pendentes"], **self.pending},
                "fetched_at": int(time.time()), "shadow_timestamp": shadow.get("timestamp")}

    def handle(self, request):
        action = request.get("action")
        if action in ("status", "refresh"):
            return self.read()
        before = self.read()
        if field(self.device, "is_online", "isOnline") not in (1, "1"):
            raise ProbeError("A TCL informou que o aparelho está offline.")
        desired = desired_state(action, str(request.get("value", "")), before["state"])
        self.iot.publish(topic=f"$aws/things/{self.device_id}/shadow/update", qos=1,
                         payload=json.dumps({"state": {"desired": desired},
                                             "clientToken": f"desktop_{time.time_ns()}"}))
        self.pending.update(desired)
        # Accepted by cloud is not a confirmation from the physical device.
        before["pending"].update(desired)
        before["message"] = "Enviado à nuvem; aguardando confirmação do aparelho."
        return before


def safe_handle(controller, request):
    try:
        return controller.handle(request)
    except ProbeError as exc:
        return {"ok": False, "error": str(exc)}
    except (BotoCoreError, ClientError):
        controller.close()
        return {"ok": False, "error": "Falha de comunicação AWS/TCL. Tente atualizar."}
    except Exception:
        # Never send raw exceptions (may contain identifiers or tokens) to the shell log.
        return {"ok": False, "error": "Resposta inesperada; não foi possível confirmar o estado."}


def emit(state):
    print(json.dumps(state, ensure_ascii=False), flush=True)


def serve():
    path = socket_path()
    if path.exists():
        with socket.socket(socket.AF_UNIX) as check:
            try:
                check.connect(str(path))
            except (ConnectionRefusedError, FileNotFoundError):
                path.unlink(missing_ok=True)
            else:
                raise ProbeError("O controlador já está em execução.")
    controller = Controller()
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(path))
        path.chmod(0o600)
        server.listen(4)
        server.settimeout(1)
        next_poll = 0
        try:
            while True:
                if time.monotonic() >= next_poll:
                    result = safe_handle(controller, {"action": "status"})
                    emit(result)
                    next_poll = time.monotonic() + 60
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(2)
                    try:
                        _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid != os.getuid():
                            continue
                        data = b""
                        while b"\n" not in data and len(data) <= 4096:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            data += chunk
                        request = json.loads(data) if len(data) <= 4096 else None
                        if not isinstance(request, dict):
                            continue
                        result = safe_handle(controller, request)
                        emit(result)
                        connection.sendall((json.dumps(result) + "\n").encode())
                        # Follow up explicit commands to observe device confirmation.
                        next_poll = time.monotonic() + (3 if request.get("action") not in ("status", "refresh") else 60)
                    except (OSError, ValueError):
                        continue
        finally:
            controller.close()
            path.unlink(missing_ok=True)


def request(action, value=""):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(90)
        client.connect(str(socket_path()))
        client.sendall((json.dumps({"action": action, "value": value}) + "\n").encode())
        with client.makefile() as response:
            result = json.loads(response.readline(65536))
    emit(result)
    return 0 if result.get("ok") else 1


def main():
    try:
        if sys.argv[1:] == ["serve"]:
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
            serve()
            return 0
        if len(sys.argv) in (2, 3):
            return request(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "")
        raise ProbeError("Use serve, status, refresh ou um controle permitido.")
    except ProbeError as exc:
        emit({"ok": False, "error": str(exc)})
    except (OSError, ValueError):
        emit({"ok": False, "error": "Controlador indisponível. Verifique se o plugin está ativo."})
    except KeyboardInterrupt:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
