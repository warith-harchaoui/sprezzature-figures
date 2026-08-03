"""
App-launch smoke test (plan §16.5): start the real Studio server as a
subprocess, confirm it serves HTTP 200 with the expected page structure,
then stop it. Deliberately not testing "every visual detail by pixel
coordinates" (plan's own caution) -- this is the "does it actually start
and render something sane" check.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytestmark = pytest.mark.slow


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_studio_server_launches_and_serves_index_page() -> None:
    port = _free_port()
    # Strip PYTEST_* env vars: NiceGUI's ui.run() detects PYTEST_CURRENT_TEST
    # (inherited from this pytest process by default) and switches into its
    # own "screen test" mode expecting NICEGUI_SCREEN_TEST_PORT, which this
    # test isn't using -- it just wants a real server to curl.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"from sprezzature_figures.studio.app import run_app; run_app(host='127.0.0.1', port={port}, show=False)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        html = None
        deadline = time.time() + 15
        last_error = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as resp:
                    html = resp.read().decode("utf-8")
                    status = resp.status
                break
            except Exception as exc:  # noqa: BLE001 - retry until the server is up or we time out
                last_error = exc
                time.sleep(0.5)
        if html is None:
            proc.terminate()
            out, _ = proc.communicate(timeout=5)
            raise AssertionError(f"server never became reachable: {last_error}\n--- subprocess output ---\n{out}")
        assert status == 200
        assert "Sprezzature Studio" in html
        assert "Import CSV, XLSX, or JSON" in html
        assert "No render yet" in html
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
