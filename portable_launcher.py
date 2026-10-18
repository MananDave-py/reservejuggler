"""Start the self-contained Windows demo and open it in a browser."""

import os
from pathlib import Path
import socket
import threading
import webbrowser
import sys


def main():
    app_data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MoneyMaxxer"
    app_data.mkdir(parents=True, exist_ok=True)
    app_folder = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    env_file = app_folder / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rjug.settings")
    os.environ.setdefault("DJANGO_DEBUG", "1")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
    os.environ.setdefault("DJANGO_DB_PATH", str(app_data / "db.sqlite3"))
    os.environ.setdefault("DJANGO_STATIC_ROOT", str(app_data / "staticfiles"))

    requested_port = int(os.environ.get("MONEYMAXXER_PORT", "8000"))
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", requested_port))
            port = requested_port
        except OSError:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

    import django
    django.setup()

    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0)
    call_command("seed_dummy_users", verbosity=0)
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    call_command("runserver", f"127.0.0.1:{port}", use_reloader=False)


if __name__ == "__main__":
    main()
