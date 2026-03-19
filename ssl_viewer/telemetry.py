from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TargetTelemetry:
    """
    Planar-array telemetry convention.

    az_deg:
        Array azimuth in the local x-y plane, counter-clockwise from +x.
        Range: [-180, 180].

    el_deg:
        Array elevation above the local x-y plane toward +z.
        Range: [0, 90].

    Local array axes used by this viewer:
        +x = in-plane reference axis shown by the arrow
        +y = in-plane axis 90 deg CCW from +x
        +z = array normal / up
    """

    az_deg: float
    el_deg: float
    confidence: float = 1.0
    target_id: int = 1
    ts_ns: int = 0
    version: int = 1

    def __post_init__(self) -> None:
        self.az_deg = float(self.az_deg)
        self.el_deg = float(self.el_deg)
        self.confidence = float(self.confidence)
        self.target_id = int(self.target_id)
        self.version = int(self.version)
        self.ts_ns = time.time_ns() if self.ts_ns == 0 else int(self.ts_ns)

        if not math.isfinite(self.az_deg):
            raise ValueError("az_deg must be finite")
        if not math.isfinite(self.el_deg):
            raise ValueError("el_deg must be finite")
        if not math.isfinite(self.confidence):
            raise ValueError("confidence must be finite")

        if not -180.0 <= self.az_deg <= 180.0:
            raise ValueError("az_deg out of range")
        if not 0.0 <= self.el_deg <= 90.0:
            raise ValueError("el_deg out of range")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence out of range")
        if self.version < 1:
            raise ValueError("version out of range")

    def to_dict(self) -> dict[str, Any]:
        return {
            "az_deg": self.az_deg,
            "el_deg": self.el_deg,
            "confidence": self.confidence,
            "target_id": self.target_id,
            "ts_ns": self.ts_ns,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetTelemetry":
        return cls(
            az_deg=data["az_deg"],
            el_deg=data["el_deg"],
            confidence=data.get("confidence", 1.0),
            target_id=data.get("target_id", 1),
            ts_ns=data.get("ts_ns", 0),
            version=data.get("version", 1),
        )

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "TargetTelemetry":
        obj = json.loads(payload.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("expected JSON object")
        return cls.from_dict(obj)

    @property
    def latency_ms(self) -> float:
        return (time.time_ns() - self.ts_ns) * 1e-6
