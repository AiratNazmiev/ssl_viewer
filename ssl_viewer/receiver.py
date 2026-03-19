from __future__ import annotations

from typing import Optional

import zmq

from .telemetry import TargetTelemetry


class Receiver:
    """
    Persistent ZMQ subscriber polled from the Streamlit refresh loop.

    This avoids a background thread, which is more fragile under Streamlit reruns.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        hwm: int = 2,
        topic: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        if hwm <= 0:
            raise ValueError("hwm must be > 0")
        if bool(username) != bool(password):
            raise ValueError("username and password must be provided together")

        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        self._sock.setsockopt(zmq.RCVHWM, int(hwm))
        self._sock.setsockopt(zmq.LINGER, 0)

        if username is not None and password is not None:
            self._sock.setsockopt_string(zmq.PLAIN_USERNAME, username)
            self._sock.setsockopt_string(zmq.PLAIN_PASSWORD, password)

        self._sock.subscribe(topic)
        self._sock.connect(endpoint)

        self.superseded = 0
        self.recv_errors = 0

    def poll_latest(self) -> TargetTelemetry | None:
        latest: TargetTelemetry | None = None

        while True:
            try:
                obj = self._sock.recv_json(flags=zmq.NOBLOCK)
                if not isinstance(obj, dict):
                    raise ValueError("expected JSON object")
                msg = TargetTelemetry.from_dict(obj)
                if latest is not None:
                    self.superseded += 1
                latest = msg

            except zmq.Again:
                break

            except Exception:
                self.recv_errors += 1
                break

        return latest

    def close(self) -> None:
        self._sock.close()
