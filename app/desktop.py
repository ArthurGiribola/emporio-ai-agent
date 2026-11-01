"""Windows WebView2 shell around the existing local Streamlit page."""

import multiprocessing
import os
import secrets
import socket
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from app.providers import _NoRedirect


def available_port():
    with socket.socket() as reservation:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def server_arguments(port, route):
    return ["streamlit", "run", str(Path(__file__).with_name("streamlit_app.py")),
            "--server.address=127.0.0.1", f"--server.port={port}",
            f"--server.baseUrlPath={route}", "--server.headless=true",
            "--browser.gatherUsageStats=false", "--client.showErrorDetails=none",
            "--server.fileWatcherType=none"]


def run_server(port, route):
    # Spawned worker, never a shell/venv redirector or a separately owned server.
    with open(os.devnull, "w") as quiet:
        os.dup2(quiet.fileno(), 1)
        os.dup2(quiet.fileno(), 2)
        from streamlit.web import cli
        sys.argv = server_arguments(port, route)
        cli.main()


def wait_until_ready(process, url, timeout=20):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    deadline = time.monotonic() + timeout
    while process.is_alive() and time.monotonic() < deadline:
        try:
            with opener.open(url + "_stcore/health", timeout=0.5) as response:
                if response.status == 200 and response.read(16).strip() == b"ok" and process.is_alive():
                    return True
        except (OSError, URLError):
            pass
        time.sleep(0.1)
    return False


def stop_server(process):
    # The direct multiprocessing handle is the ownership boundary. No PID or
    # port-based kill, process-name matching, taskkill /T, or existing-server reuse.
    if process.is_alive():
        process.terminate()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)
    process.close()


@contextmanager
def local_server():
    context = multiprocessing.get_context("spawn")
    for _ in range(3):
        port = available_port()
        # An unpredictable route prevents a port-race listener from satisfying
        # another server's generic health URL. Readiness also requires our child.
        route = "desktop-" + secrets.token_hex(16)
        url = f"http://127.0.0.1:{port}/{route}/"
        process = context.Process(target=run_server, args=(port, route), daemon=True)
        process.start()
        try:
            if wait_until_ready(process, url):
                yield url
                return
        finally:
            stop_server(process)
    raise RuntimeError("Local interface could not start on an available loopback port")


def main():
    if sys.platform != "win32":
        print("The desktop launcher supports Windows. Use python -m app.web for the browser interface.")
        return 2
    try:
        import webview
        with local_server() as url:
            # Default x/y center on screen. Keep normal native window chrome.
            webview.create_window("Empório da Música", url, width=560, height=720,
                                  min_size=(420, 640), resizable=True,
                                  background_color="#000000", text_select=True)
            webview.start(gui="edgechromium", debug=False, private_mode=True)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        print('Desktop startup failed. Install ".[desktop]" with Python 3.12 and ensure Microsoft Edge WebView2 Runtime is installed.')
        return 2


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
