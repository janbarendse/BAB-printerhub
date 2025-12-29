"""
Named-pipe IPC utilities for Core <-> UI communication.

Uses multiprocessing.connection for Windows named pipes with an auth key.
"""

from __future__ import annotations

import logging
import secrets
import threading
from typing import Callable, Dict, Any, Optional

from multiprocessing.connection import Listener

logger = logging.getLogger(__name__)


def make_pipe_name(prefix: str = "BAB_PrintHub_IPC") -> str:
    """Generate a unique Windows named pipe path."""
    token = secrets.token_hex(8)
    return rf"\\.\pipe\{prefix}_{token}"


def make_auth_key(size: int = 16) -> bytes:
    """Generate a random auth key for the IPC channel."""
    return secrets.token_bytes(size)


class PipeServer:
    """Simple named-pipe server that dispatches JSON-like dict requests."""

    def __init__(
        self,
        pipe_name: str,
        auth_key: bytes,
        handler: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.pipe_name = pipe_name
        self.auth_key = auth_key
        self._handler = handler
        self._log = log or logger
        self._stop_event = threading.Event()
        self._listener = None
        self._thread = None

    def start(self) -> None:
        """Start the server in a background thread."""
        if self._thread:
            return
        self._listener = Listener(self.pipe_name, authkey=self.auth_key)
        self._thread = threading.Thread(target=self._serve, daemon=True, name="IPCServer")
        self._thread.start()
        self._log.info("IPC server listening on %s", self.pipe_name)

    def stop(self) -> None:
        """Stop the server and close the listener."""
        self._stop_event.set()
        if self._listener:
            try:
                self._listener.close()
            except Exception:
                pass

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                conn = self._listener.accept()
            except Exception as exc:
                if not self._stop_event.is_set():
                    self._log.warning("IPC accept failed: %s", exc)
                break
            threading.Thread(
                target=self._handle_conn,
                args=(conn,),
                daemon=True,
                name="IPCClient",
            ).start()

    def _handle_conn(self, conn) -> None:
        with conn:
            while not self._stop_event.is_set():
                try:
                    msg = conn.recv()
                except EOFError:
                    break
                except Exception as exc:
                    self._log.warning("IPC recv failed: %s", exc)
                    break

                response = self._dispatch(msg)

                try:
                    conn.send(response)
                except Exception as exc:
                    self._log.warning("IPC send failed: %s", exc)
                    break

    def _dispatch(self, msg) -> Dict[str, Any]:
        if not isinstance(msg, dict):
            return {"success": False, "error": "Invalid IPC message"}

        action = msg.get("action")
        payload = msg.get("payload") or {}
        if not action:
            return {"success": False, "error": "Missing action"}

        try:
            return self._handler(action, payload)
        except Exception as exc:
            self._log.exception("IPC handler failed for %s", action)
            return {"success": False, "error": str(exc)}
