"""Camera-target smoothing adapted from algometrix/vertical_video_convertor.

Distance-scaled easing, speed cap (one crop-width per second), refocus band,
and integer-crop anti-jitter.
"""

from __future__ import annotations

import math


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class TargetSmoother:
    REFOCUS_BAND_FRACTION = 0.03
    SOFT_ZONE_RADIUS = 0.005
    MIN_ALPHA = 0.06
    MAX_ALPHA = 0.40
    FAR_THRESHOLD = 0.15
    SNAP_DISTANCE_PX = 0.75

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        fps: float,
        refocus_band_fraction: float | None = None,
    ) -> None:
        if frame_width <= 0 or frame_height <= 0 or crop_width <= 0 or fps <= 0:
            raise ValueError("frame dimensions, crop width and fps must be positive")
        if refocus_band_fraction is None:
            refocus_band_fraction = self.REFOCUS_BAND_FRACTION
        if refocus_band_fraction < 0:
            raise ValueError("refocus_band_fraction must be >= 0")
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.max_step_px = max(1.0, crop_width / fps)
        self.refocus_band_px = frame_width * refocus_band_fraction
        self.x = frame_width / 2.0
        self.y = frame_height / 2.0
        self._held_target: tuple[float, float] = (self.x, self.y)

    def reset(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self._held_target = (self.x, self.y)

    def update(self, target_x: float | None = None, target_y: float | None = None) -> tuple[float, float]:
        if target_x is not None and target_y is not None:
            held_x, held_y = self._held_target
            dx = float(target_x) - held_x
            dy = float(target_y) - held_y
            distance = math.hypot(dx, dy)
            if distance > self.refocus_band_px:
                pull = (distance - self.refocus_band_px) / distance
                self._held_target = (held_x + dx * pull, held_y + dy * pull)

        tx, ty = self._held_target
        dx = tx - self.x
        dy = ty - self.y
        distance = math.hypot(dx, dy)

        if distance <= self.SNAP_DISTANCE_PX:
            self.x, self.y = tx, ty
            return self.x, self.y

        normalized = distance / self.frame_width
        ease = 1.0 - (1.0 - min(1.0, normalized / self.FAR_THRESHOLD)) ** 3
        alpha = self.MIN_ALPHA + (self.MAX_ALPHA - self.MIN_ALPHA) * ease
        if normalized < self.SOFT_ZONE_RADIUS:
            alpha *= _smoothstep(normalized / self.SOFT_ZONE_RADIUS)

        step_x = dx * alpha
        step_y = dy * alpha
        step = math.hypot(step_x, step_y)
        if step > self.max_step_px:
            scale = self.max_step_px / step
            step_x *= scale
            step_y *= scale

        self.x += step_x
        self.y += step_y
        return self.x, self.y


class CropSmoother:
    SMALL_MOVE_PX = 2
    SMALL_MOVE_BLEND = 0.4
    LARGE_MOVE_BLEND = 0.97
    OUTPUT_HYSTERESIS_PX = 0.75

    def __init__(self) -> None:
        self._left: float | None = None
        self._top: float | None = None
        self._out_left = 0
        self._out_top = 0

    def reset(self) -> None:
        self._left = None
        self._top = None

    def update(self, left: int, top: int) -> tuple[int, int]:
        if self._left is None or self._top is None:
            self._left, self._top = float(left), float(top)
            self._out_left, self._out_top = left, top
            return left, top

        def blend(previous: float, new: int) -> float:
            delta = new - previous
            factor = self.SMALL_MOVE_BLEND if abs(delta) <= self.SMALL_MOVE_PX else self.LARGE_MOVE_BLEND
            return previous + factor * delta

        self._left = blend(self._left, left)
        self._top = blend(self._top, top)
        if abs(self._left - self._out_left) > self.OUTPUT_HYSTERESIS_PX:
            self._out_left = round(self._left)
        if abs(self._top - self._out_top) > self.OUTPUT_HYSTERESIS_PX:
            self._out_top = round(self._top)
        return self._out_left, self._out_top
