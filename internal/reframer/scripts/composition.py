"""Visual composition and camera motion analyzer for Clipreator.

Analyzes original 16:9 shot composition:
- Optical flow global camera motion (pans, zooms, tilts)
- Visual salience and edge/contrast energy density
- Framing priors (centrality, rule-of-thirds)
- Subject size and spatial dominance
- Temporal persistence of visual subjects across frames
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


@dataclass
class CameraMotion:
    pan_x: float = 0.0      # Positive = camera panning right
    tilt_y: float = 0.0     # Positive = camera tilting down
    magnitude: float = 0.0  # Overall motion magnitude


class CompositionAnalyzer:
    FLOW_DOWNSCALE = (160, 90)

    def __init__(self, frame_width: int, frame_height: int) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._prev_gray: np.ndarray | None = None
        self.current_motion = CameraMotion()
        self._persistence_map: dict[str, float] = {}

    def reset(self) -> None:
        self._prev_gray = None
        self.current_motion = CameraMotion()
        self._persistence_map.clear()

    def update_frame(self, frame_bgr: np.ndarray) -> CameraMotion:
        """Estimates global camera motion using downsampled optical flow."""
        small = cv2.resize(frame_bgr, self.FLOW_DOWNSCALE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None:
            self._prev_gray = gray
            self.current_motion = CameraMotion()
            return self.current_motion

        # Farneback optical flow on small frame (takes <1ms)
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=2,
            winsize=13,
            iterations=2,
            poly_n=5,
            poly_sigma=1.1,
            flags=0,
        )
        self._prev_gray = gray

        # Robust median flow vector represents global camera movement
        flow_x = flow[..., 0]
        flow_y = flow[..., 1]
        med_x = float(np.median(flow_x))
        med_y = float(np.median(flow_y))

        # Filter out tiny noise
        if abs(med_x) < 0.25:
            med_x = 0.0
        if abs(med_y) < 0.25:
            med_y = 0.0

        mag = math.hypot(med_x, med_y)
        self.current_motion = CameraMotion(pan_x=med_x, tilt_y=med_y, magnitude=mag)
        return self.current_motion

    def compute_salience_map(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Computes a lightweight visual salience / detail map.
        
        Uses Sobel gradients + local luminance contrast for high-detail areas.
        """
        small = cv2.resize(frame_bgr, (320, 180), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(grad_x, grad_y)
        blurred = cv2.GaussianBlur(mag, (15, 15), 0)
        norm = cv2.normalize(blurred, None, 0.0, 1.0, cv2.NORM_MINMAX)
        return norm

    def score_framing(self, bbox: Sequence[float]) -> float:
        """Evaluates framing quality in the original 16:9 frame.
        
        High scores for rule-of-thirds and central placement;
        penalizes subjects clipped near extreme edges.
        """
        x1, y1, x2, y2 = bbox[:4]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        rel_x = cx / float(self.frame_width)
        rel_y = cy / float(self.frame_height)

        # Distance to center
        dist_center = abs(rel_x - 0.5)

        # Rule of thirds lines are at 0.333 and 0.667
        dist_thirds = min(abs(rel_x - 0.333), abs(rel_x - 0.667))

        # Composition prior prefers center (1.0) and thirds (0.9), penalizes extreme edges
        composition_score = max(
            1.0 - 1.8 * (dist_center ** 2),
            0.92 - 1.5 * (dist_thirds ** 2),
        )

        # Extreme edge penalty if pushed against boundaries
        if rel_x < 0.08 or rel_x > 0.92 or rel_y < 0.05 or rel_y > 0.95:
            composition_score *= 0.5

        return max(0.0, min(1.0, composition_score))

    def score_size(self, bbox: Sequence[float]) -> float:
        """Measures visual prominence based on normalized bounding box area."""
        x1, y1, x2, y2 = bbox[:4]
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        frame_area = float(self.frame_width * self.frame_height)
        frac = area / frame_area

        # In typical shots, a subject occupying 8% to 40% of the frame is the key focus.
        # Below 2% is tiny background clutter; above 70% is extreme fill.
        if frac <= 0.02:
            return frac * 25.0  # 0 to 0.5
        elif frac <= 0.35:
            return 0.5 + (frac - 0.02) / 0.33 * 0.5  # 0.5 to 1.0
        else:
            return 1.0

    def score_pan_alignment(self, bbox: Sequence[float]) -> float:
        """Rewards targets aligned with camera pan direction.
        
        If the original camera is panning right (pan_x > 0), targets on the right side
        of the frame or in the motion direction receive an operator-intent boost.
        """
        if abs(self.current_motion.pan_x) < 0.3:
            return 0.0

        x1, _, x2, _ = bbox[:4]
        cx = (x1 + x2) / 2.0
        rel_x = (cx - self.frame_width / 2.0) / (self.frame_width / 2.0)  # -1.0 to 1.0

        # If pan is right (>0) and subject is to the right (>0), alignment is positive
        # Note: In optical flow of background, camera panning right causes image features
        # to shift LEFT (flow_x < 0). So camera pan direction = -flow_x.
        camera_pan_dir = -self.current_motion.pan_x
        alignment = rel_x * (1.0 if camera_pan_dir > 0 else -1.0)
        return max(-1.0, min(1.0, alignment))

    def score_salience(self, salience_map: np.ndarray, crop_left: int, crop_top: int, crop_w: int, crop_h: int) -> float:
        """Calculates average visual salience density inside candidate crop window."""
        h, w = salience_map.shape[:2]
        # Map 16:9 crop coords to salience map coords
        sx1 = int(max(0, min(w - 1, (crop_left / self.frame_width) * w)))
        sy1 = int(max(0, min(h - 1, (crop_top / self.frame_height) * h)))
        sx2 = int(max(sx1 + 1, min(w, ((crop_left + crop_w) / self.frame_width) * w)))
        sy2 = int(max(sy1 + 1, min(h, ((crop_top + crop_h) / self.frame_height) * h)))

        region = salience_map[sy1:sy2, sx1:sx2]
        if region.size == 0:
            return 0.5
        return float(np.mean(region))
