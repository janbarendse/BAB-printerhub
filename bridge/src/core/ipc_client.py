"""
Named-pipe IPC client for UI -> Core requests.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
from typing import Dict, Any, Optional

from multiprocessing.connection import Client

logger = logging.getLogger(__name__)


def _decode_auth_key(value: str) -> Optional[bytes]:
    if not value:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        try:
            return base64.b64decode(value)
        except Exception:
            return None


class IpcClient:
    """Simple IPC client with a persistent connection and thread safety."""

    def __init__(self, pipe_name: Optional[str] = None, auth_key: Optional[bytes] = None) -> None:
        self.pipe_name = pipe_name or os.environ.get("BAB_PIPE_NAME")
        self.auth_key = auth_key or _decode_auth_key(os.environ.get("BAB_PIPE_KEY", ""))
        self._lock = threading.Lock()
        self._conn = None

    def request(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.pipe_name or not self.auth_key:
            return {"success": False, "error": "IPC is not configured"}

        with self._lock:
            if self._conn is None:
                try:
                    self._conn = Client(self.pipe_name, authkey=self.auth_key)
                except Exception as exc:
                    logger.error("IPC connection failed: %s", exc)
                    self._conn = None
                    return {"success": False, "error": f"IPC connection failed: {exc}"}

            try:
                self._conn.send({"action": action, "payload": payload or {}})
                return self._conn.recv()
            except Exception as exc:
                logger.error("IPC request failed: %s", exc)
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
                return {"success": False, "error": f"IPC request failed: {exc}"}
