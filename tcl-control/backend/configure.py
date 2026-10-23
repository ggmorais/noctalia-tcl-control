"""Interactive credential setup. Never receives secrets in command-line arguments."""

import getpass
import json
import os
import sys
import warnings

from credentials import credentials_path


def main():
    path = credentials_path()
    if path.exists():
        print(f"Credentials already exist at {path}; leaving them unchanged.")
        return 0
    if not sys.stdin.isatty():
        print("Run setup in an interactive terminal to configure your TCL account.")
        return 1
    print("Unofficial TCL Home integration. A separate shared account is recommended.")
    print("Credentials are saved as plaintext readable only by your Linux user.")
    try:
        login = input("TCL Home email/username: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("TCL Home password (hidden): ")
        if not login or not password:
            print("Username and password are required.")
            return 1
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        text = f"TCL_LOGIN={json.dumps(login)}\nTCL_PASSWORD={json.dumps(password)}\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as target:
            target.write(text)
        print(f"Credentials saved at {path}. No commands sent to your AC.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
    except getpass.GetPassWarning:
        print("Cannot hide input. Use a normal terminal; credentials were not saved.")
    except OSError:
        print("Unable to create the credentials file. Existing files were not overwritten.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
