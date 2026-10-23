"""Minimal local dotenv reader; never executes shell syntax or logs values."""

import os
import json
from pathlib import Path

from probe import ProbeError


def credentials_path():
    override = os.environ.get("TCL_ENV_FILE")
    if override:
        return Path(override).expanduser()
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "tcl-control" / "credentials.env"


def load_credentials(path=None):
    path = Path(path) if path is not None else credentials_path()
    values = {}
    if path.exists():
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            raise ProbeError("Credentials must be owned by you, not symlinked, and have mode 600.")
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, sep, value = line.partition("=")
            key = key.strip()
            if sep and key in ("TCL_LOGIN", "TCL_PASSWORD"):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = json.loads(value)
                elif len(value) >= 2 and value[0] == value[-1] == "'":
                    value = value[1:-1]
                values[key] = value
    username = os.environ.get("TCL_LOGIN", values.get("TCL_LOGIN", ""))
    password = os.environ.get("TCL_PASSWORD", values.get("TCL_PASSWORD", ""))
    if not username or not password:
        raise ProbeError("Configure TCL_LOGIN and TCL_PASSWORD with setup.sh first.")
    return username, password
