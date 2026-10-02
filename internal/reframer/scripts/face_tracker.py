"""Sticky subject tracking with two-person grouping.

Selection and dropout-hold are adapted from algometrix/vertical_video_convertor.
When two (or more) people fit inside the 9:16 window they are kept together;
otherwise the camera sticks to one primary subject instead of ping-ponging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class DetectedFace:
    bbox: Sequence[float]  # x1, y1, x2, y2
    det_score: float = 1.0


def _center(face: DetectedFace) -> tuple[float, float]:
    x1, y1, x2, y2 = (float(v) for v in face.bbox[:4])
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _score(face: DetectedFace) -> float:
    x1, y1, x2, y2 = (float(v) for v in face.bbox[:4])
    area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return area * float(face.det_score)


def _group_bounds(faces: Sequence[DetectedFace]) -> tuple[float, float, float, float]:
    x1 = min(float(f.bbox[0]) for f in faces)
    y1 = min(float(f.bbox[1]) for f in faces)
    x2 = max(float(f.bbox[2]) for f in faces)
    y2 = max(float(f.bbox[3]) for f in faces)
    return x1, y1, x2, y2


def _group_center(faces: Sequence[DetectedFace]) -> tuple[float, float]:
    x1, y1, x2, y2 = _group_bounds(faces)
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _group_score(faces: Sequence[DetectedFace]) -> float:
    raw = sum(_score(f) for f in faces)
    # Prefer keeping extra people when they still fit.
    return raw * (1.0 + 0.35 * (len(faces) - 1))


class FaceTracker:
    STICKY_TOLERANCE_FRACTION = 0.15
    STICKY_SWITCH_RATIO = 1.5
    GROUP_PADDING_FRACTION = 0.12  # extra width so faces are not flush with the crop edge

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        hold_seconds: float = 2.0,
    ) -> None:
        if frame_width <= 0 or frame_height <= 0 or crop_width <= 0:
            raise ValueError("frame dimensions and crop width must be positive")
        if hold_seconds < 0:
            raise ValueError("hold_seconds must be >= 0")
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.crop_width = crop_width
        self.hold_seconds = hold_seconds
        self._last_center: tuple[float, float] | None = None
        self._last_seen_at: float | None = None
        self._last_count = 0

    def reset(self) -> None:
        self._last_center = None
        self._last_seen_at = None
        self._last_count = 0

    @property
    def has_face(self) -> bool:
        return self._last_center is not None

    def update(self, faces: Sequence[DetectedFace], now: float) -> tuple[float, float] | None:
        if faces:
            group = self._select(faces)
            self._last_center = _group_center(group)
            self._last_seen_at = now
            self._last_count = len(group)
            return self._last_center

        if self._last_center is not None and self._last_seen_at is not None:
            if now - self._last_seen_at <= self.hold_seconds:
                return self._last_center
        self.reset()
        return None

    def _fits(self, faces: Sequence[DetectedFace]) -> bool:
        x1, _, x2, _ = _group_bounds(faces)
        padding = self.crop_width * self.GROUP_PADDING_FRACTION
        return (x2 - x1) + padding <= self.crop_width

    def _candidate_groups(self, faces: Sequence[DetectedFace]) -> list[list[DetectedFace]]:
        ordered = sorted(faces, key=lambda f: _center(f)[0])
        groups: list[list[DetectedFace]] = []
        n = len(ordered)
        for i in range(n):
            for j in range(i, n):
                group = ordered[i : j + 1]
                if self._fits(group):
                    groups.append(group)
        if not groups:
            groups = [[max(faces, key=_score)]]
        return groups

    def _select(self, faces: Sequence[DetectedFace]) -> list[DetectedFace]:
        groups = self._candidate_groups(faces)
        best = max(groups, key=_group_score)
        if self._last_center is None:
            return best

        tolerance = self.frame_width * self.STICKY_TOLERANCE_FRACTION
        incumbent = None
        incumbent_distance = tolerance
        for group in groups:
            cx, cy = _group_center(group)
            distance = math.hypot(cx - self._last_center[0], cy - self._last_center[1])
            # Prefer matching the previous subject count when distances are similar.
            if self._last_count and abs(len(group) - self._last_count) > 0:
                distance += tolerance * 0.15
            if distance <= incumbent_distance:
                incumbent = group
                incumbent_distance = distance

        if incumbent is None or incumbent is best:
            return best
        if _group_score(best) >= self.STICKY_SWITCH_RATIO * _group_score(incumbent):
            return best
        return incumbent
