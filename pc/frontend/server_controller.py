from __future__ import annotations

import atexit
import socket
import time
from typing import Optional

from server import API_PORT as SERVER_API_PORT, start_server_in_thread

from .constants import SERVER_BIND_HOST, SERVER_PROBE_HOST, SERVER_START_TIMEOUT


class EmbeddedServerController:
    def __init__(
        self,
        *,
        bind_host: str = SERVER_BIND_HOST,
        probe_host: str = SERVER_PROBE_HOST,
        port: int = SERVER_API_PORT,
    ) -> None:
        self.bind_host = bind_host
        self.probe_host = probe_host
        self.port = port
        self._server = None
        self._thread = None
        self._exit_hook_registered = False

    def start(self) -> None:
        if self._is_listening():
            return
        server, thread = start_server_in_thread(
            host=self.bind_host,
            port=self.port,
            log_level="warning",
            enable_mdns=False,
        )
        self._server = server
        self._thread = thread
        if not self._exit_hook_registered:
            atexit.register(self.stop)
            self._exit_hook_registered = True
        self._wait_until_ready()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.should_exit = True
        self._server.force_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def _wait_until_ready(self) -> None:
        deadline = time.time() + SERVER_START_TIMEOUT
        while time.time() < deadline:
            if self._is_listening():
                return
            if self._server and self._server.should_exit:
                raise RuntimeError("Server stopped before finishing startup")
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for server to listen on {self.probe_host}:{self.port}")

    def _is_listening(self) -> bool:
        try:
            with socket.create_connection((self.probe_host, self.port), timeout=0.5):
                return True
        except OSError:
            return False
