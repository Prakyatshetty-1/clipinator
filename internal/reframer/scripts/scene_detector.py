"""Hard scene-cut detection adapted from algometrix/vertical_video_convertor."""

from __future__ import annotations

import cv2
import numpy as np


class SceneCutDetector:
    DOWNSCALE_SIZE = (96, 54)

    def __init__(self, threshold: float = 28.0) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        self.threshold = threshold
        self._previous: np.ndarray | None = None

    def reset(self) -> None:
        self._previous = None

    def update(self, frame_bgr: np.ndarray) -> bool:
        small = cv2.resize(frame_bgr, self.DOWNSCALE_SIZE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        previous = self._previous
        self._previous = gray
        if previous is None:
            return False

        mean_diff = float(np.mean(cv2.absdiff(gray, previous)))
        return mean_diff >= self.threshold
