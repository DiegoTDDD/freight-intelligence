"""Start or reuse the loopback dashboard without invoking the data pipeline."""

import argparse
import importlib.util
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def healthy(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
            return response.status == 200 and response.read(64).strip() == b"ok"
    except (OSError, urllib.error.URLError):
        return False


def occupied(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def ensure_dashboard(port=8501, timeout=25):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("A porta deve estar entre 1024 e 65535")
    url = f"http://127.0.0.1:{port}/"
    if healthy(port):
        return url, False
    if occupied(port):
        raise RuntimeError(f"A porta {port} esta ocupada por um servico que nao responde como painel")
    if importlib.util.find_spec("streamlit") is None:
        raise RuntimeError("Streamlit indisponivel neste ambiente Python; instale os extras app do projeto")
    app = ROOT / "dashboards/app.py"
    if not app.is_file():
        raise RuntimeError("Arquivo do painel indisponivel; execute a partir de uma copia do repositorio")
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    options = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (logs / "dashboard.log").open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(app), "--server.address", "127.0.0.1",
             "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **options,
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if healthy(port):
            return url, True
        if process.poll() is not None:
            raise RuntimeError("O painel encerrou durante a abertura. Consulte logs/dashboard.log")
        time.sleep(0.25)
    # Do not kill a potentially slow startup or any existing user process.
    raise RuntimeError("O painel ainda nao respondeu. Consulte logs/dashboard.log antes de tentar novamente")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        url, started = ensure_dashboard(args.port)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Nao foi possivel abrir o painel: {error}\n")
    print("Painel iniciado." if started else "Painel ja estava funcionando.")
    print(url)
    if not args.no_browser:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
