"""Multi-entity tracker with persistent IDs, velocity projection, and occlusion coasting.

Maintains identity consistency across frames for people, faces, and objects.
Avoids identity swapping when two subjects cross or move close together.
Handles scene cuts by resetting tracking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from detector import DetectedEntity


def calculate_iou(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """Calculates Intersection over Union (IoU) between two [x1, y1, x2, y2] boxes."""
    ax1, ay1, ax2, ay2 = box_a[:4]
    bx1, by1, bx2, by2 = box_b[:4]

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(0.0, (bx2 - bx1) * (by2 - by1))
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def calculate_distance(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """Normalized Euclidean distance between center points of two boxes."""
    ax1, ay1, ax2, ay2 = box_a[:4]
    bx1, by1, bx2, by2 = box_b[:4]
    ca_x, ca_y = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
    cb_x, cb_y = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
    return math.hypot(ca_x - cb_x, ca_y - cb_y)


@dataclass
class TrackedEntity:
    track_id: int
    category: str  # 'face', 'person', 'object'
    label: str     # 'face', 'person', 'cell phone', etc.
    bbox: list[float]  # [x1, y1, x2, y2]
    score: float
    first_seen: float
    last_seen: float
    missed_frames: int = 0
    hits: int = 1
    velocity: list[float] = field(default_factory=lambda: [0.0, 0.0])  # [vx, vy] per frame
    mouth_motion_score: float = 0.0
    speaker_score: float = 0.0
    is_active_speaker: bool = False

    @property
    def cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2.0

    @property
    def cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2.0

    @property
    def width(self) -> float:
        return max(1.0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return max(1.0, self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return self.width * self.height

    def project(self, frame_w: int, frame_h: int) -> list[float]:
        """Projects bbox forward by estimated velocity during coasting."""
        vx, vy = self.velocity
        px1 = max(0.0, min(float(frame_w), self.bbox[0] + vx))
        py1 = max(0.0, min(float(frame_h), self.bbox[1] + vy))
        px2 = max(0.0, min(float(frame_w), self.bbox[2] + vx))
        py2 = max(0.0, min(float(frame_h), self.bbox[3] + vy))
        return [px1, py1, px2, py2]


class MultiEntityTracker:
    IOU_MATCH_THRESHOLD = 0.20
    DISTANCE_MATCH_FRACTION = 0.15  # Max center distance as fraction of frame width
    MAX_MISSED_FRAMES = 15          # Hold track up to 0.5s at 30fps

    def __init__(self, frame_width: int, frame_height: int) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._next_id: int = 1
        self.tracks: dict[int, TrackedEntity] = {}

    def reset(self) -> None:
        """Clears all tracks on scene cuts or camera resets."""
        self.tracks.clear()

    def update(self, detections: Sequence[DetectedEntity], timestamp: float) -> list[TrackedEntity]:
        """Associates new detections with existing tracks or creates new tracks."""
        # 1. Project existing tracks
        for t in self.tracks.values():
            t.bbox = t.project(self.frame_width, self.frame_height)
            t.missed_frames += 1

        unmatched_detections = list(range(len(detections)))
        unmatched_tracks = list(self.tracks.keys())

        # 2. Match detections by category and IoU + distance
        matched: list[tuple[int, int]] = []  # (track_id, det_idx)

        # Build candidate match scores
        for track_id in unmatched_tracks:
            track = self.tracks[track_id]
            best_det_idx = -1
            best_score = -1.0

            for det_idx in unmatched_detections:
                det = detections[det_idx]
                # Category must match ('face' with 'face', 'person' with 'person')
                if track.category != det.category:
                    continue

                iou = calculate_iou(track.bbox, det.bbox)
                dist = calculate_distance(track.bbox, det.bbox)
                norm_dist = dist / float(self.frame_width)

                # Matching score combines IoU and spatial proximity
                if iou >= self.IOU_MATCH_THRESHOLD or norm_dist <= self.DISTANCE_MATCH_FRACTION:
                    score = iou * 0.70 + max(0.0, 1.0 - norm_dist / self.DISTANCE_MATCH_FRACTION) * 0.30
                    if score > best_score:
                        best_score = score
                        best_det_idx = det_idx

            if best_det_idx != -1 and best_score > 0.25:
                matched.append((track_id, best_det_idx))

        # Apply matches
        matched_det_indices = set()
        for track_id, det_idx in matched:
            if det_idx in matched_det_indices:
                continue
            matched_det_indices.add(det_idx)
            if det_idx in unmatched_detections:
                unmatched_detections.remove(det_idx)

            det = detections[det_idx]
            track = self.tracks[track_id]

            # Update velocity using smooth alpha
            old_cx, old_cy = track.cx, track.cy
            new_cx = (det.bbox[0] + det.bbox[2]) / 2.0
            new_cy = (det.bbox[1] + det.bbox[3]) / 2.0
            vx = (new_cx - old_cx) * 0.6 + track.velocity[0] * 0.4
            vy = (new_cy - old_cy) * 0.6 + track.velocity[1] * 0.4

            # Update track
            track.bbox = [float(v) for v in det.bbox[:4]]
            track.score = float(det.score)
            track.label = det.label
            track.last_seen = timestamp
            track.missed_frames = 0
            track.hits += 1
            track.velocity = [vx, vy]

        # 3. Create new tracks for unmatched detections
        for det_idx in unmatched_detections:
            det = detections[det_idx]
            new_track = TrackedEntity(
                track_id=self._next_id,
                category=det.category,
                label=det.label,
                bbox=[float(v) for v in det.bbox[:4]],
                score=float(det.score),
                first_seen=timestamp,
                last_seen=timestamp,
            )
            self.tracks[self._next_id] = new_track
            self._next_id += 1

        # 4. Prune stale tracks exceeding max missed frames
        dead_ids = [
            tid for tid, track in self.tracks.items()
            if track.missed_frames > self.MAX_MISSED_FRAMES
        ]
        for tid in dead_ids:
            del self.tracks[tid]

        # Return active tracks
        return list(self.tracks.values())
