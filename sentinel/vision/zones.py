"""Virtual checkpoint zones: pure geometry, no camera or model dependencies.

All coordinates are normalized to 0.0 .. 1.0 so zones are resolution-independent.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

from sentinel.vision.config import ZoneConfigError

Point = tuple[float, float]
Box = tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized)


def normalize_box(box_px: Sequence[float], width: int, height: int) -> Box:
    """Convert a pixel (x1, y1, x2, y2) box to normalized, clamped 0..1 coordinates."""
    if width <= 0 or height <= 0:
        raise ValueError("frame width and height must be positive")
    if len(box_px) != 4:
        raise ValueError("box must have four values: x1, y1, x2, y2")
    x1, y1, x2, y2 = (float(v) for v in box_px)
    nx1, nx2 = sorted((x1 / width, x2 / width))
    ny1, ny2 = sorted((y1 / height, y2 / height))

    def clamp(v: float) -> float:
        return min(1.0, max(0.0, v))

    return clamp(nx1), clamp(ny1), clamp(nx2), clamp(ny2)


def ground_point(box: Box) -> Point:
    """Bottom-center of a normalized box: the preferred ground-position estimate."""
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, max(y1, y2)


def center_point(box: Box) -> Point:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def to_pixels(box: Box, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)


@dataclass(frozen=True)
class Zone:
    zone_id: str
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, point: Point) -> bool:
        """Inclusive of the zone edges."""
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    @property
    def box(self) -> Box:
        return self.x1, self.y1, self.x2, self.y2

    @property
    def label(self) -> str:
        return f"{self.zone_id} {self.name}"

    def overlaps(self, other: "Zone") -> bool:
        # Touching edges do not count as overlap.
        return self.x1 < other.x2 and other.x1 < self.x2 and self.y1 < other.y2 and other.y1 < self.y2


class ZoneSet:
    """An ordered, non-overlapping collection of zones."""

    def __init__(self, zones: Sequence[Zone]):
        if not zones:
            raise ZoneConfigError("Zone configuration contains no zones.")
        seen: set[str] = set()
        for z in zones:
            if z.zone_id in seen:
                raise ZoneConfigError(f"Duplicate zone id '{z.zone_id}'.")
            seen.add(z.zone_id)
        for i, a in enumerate(zones):
            for b in zones[i + 1:]:
                if a.overlaps(b):
                    raise ZoneConfigError(f"Zones '{a.zone_id}' and '{b.zone_id}' overlap; zones must be disjoint.")
        self._zones = tuple(zones)

    def __iter__(self) -> Iterator[Zone]:
        return iter(self._zones)

    def __len__(self) -> int:
        return len(self._zones)

    @property
    def ids(self) -> list[str]:
        return [z.zone_id for z in self._zones]

    def get(self, zone_id: str) -> Zone:
        for z in self._zones:
            if z.zone_id == zone_id:
                return z
        raise KeyError(zone_id)

    def locate(self, point: Point) -> Zone | None:
        for z in self._zones:
            if z.contains(point):
                return z
        return None

    # ---- loading -------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Any) -> "ZoneSet":
        if not isinstance(data, dict) or not data:
            raise ZoneConfigError("Zone config must be a non-empty JSON object keyed by zone id (e.g. \"A\").")
        zones: list[Zone] = []
        for zone_id, spec in data.items():
            if not isinstance(spec, dict):
                raise ZoneConfigError(f"Zone '{zone_id}' must be an object with name, x1, y1, x2, y2.")
            name = spec.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ZoneConfigError(f"Zone '{zone_id}' needs a non-empty string 'name'.")
            coords: dict[str, float] = {}
            for key in ("x1", "y1", "x2", "y2"):
                value = spec.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ZoneConfigError(f"Zone '{zone_id}': '{key}' must be a finite number, got {value!r}.")
                if not 0.0 <= value <= 1.0:
                    raise ZoneConfigError(f"Zone '{zone_id}': '{key}'={value} is outside the normalized range 0.0 .. 1.0.")
                coords[key] = float(value)
            if coords["x1"] >= coords["x2"] or coords["y1"] >= coords["y2"]:
                raise ZoneConfigError(f"Zone '{zone_id}': requires x1 < x2 and y1 < y2.")
            zones.append(Zone(zone_id=str(zone_id), name=name.strip(), **coords))
        return cls(zones)

    @classmethod
    def load(cls, path: str | Path) -> "ZoneSet":
        p = Path(path)
        if not p.is_file():
            raise ZoneConfigError(f"Zone config file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            raise ZoneConfigError(f"Could not read zone config {p}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ZoneConfigError(f"Zone config {p} is not valid JSON: {exc}") from exc
        return cls.from_dict(data)
