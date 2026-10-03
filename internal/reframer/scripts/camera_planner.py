"""Intelligent Camera Planner for Clipreator 9:16 Reframing.

Evaluates multi-modal visual targets:
- Original camera composition and operator intent (centrality, size, persistence, optical flow pan alignment)
- Active speaker cues (mouth motion + audio energy)
- Salient objects and actions (food, money, packages, props, challenges)
- Multi-person grouping (keeping both when they fit within 9:16)
- Hysteresis, dwell-time locking, and scene-cut resets to eliminate jitter and ping-ponging
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from composition import CompositionAnalyzer
from detector import DetectedEntity
from speaker import SpeakerAnalyzer, SpeakerCue


@dataclass
class TargetCandidate:
    id: str
    target_type: str  # 'group', 'person_object', 'person', 'face', 'object', 'center'
    bbox: list[float]  # [x1, y1, x2, y2]
    cx: float
    cy: float
    entities: list[DetectedEntity] = field(default_factory=list)
    score: float = 0.0
    speaker_score: float = 0.0
    original_focus_score: float = 0.0
    action_score: float = 0.0
    salience_score: float = 0.0


class IntelligentCameraPlanner:
    SWITCH_MARGIN = 0.28          # New target must beat incumbent by 28% to trigger switch
    MIN_DWELL_SECONDS = 1.25      # Camera stays on a target for at least 1.25s before voluntary switch
    GROUP_PADDING_FRACTION = 0.12 # Edge padding for 2-person group crop
    HEADROOM_FRACTION = 0.42      # Vertical headroom placement

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        crop_height: int,
        hold_seconds: float = 2.0,
    ) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.crop_width = crop_width
        self.crop_height = crop_height
        self.hold_seconds = hold_seconds

        self.composition = CompositionAnalyzer(frame_width, frame_height)
        self.speaker = SpeakerAnalyzer()

        self._active_target_id: str | None = None
        self._active_target_center: tuple[float, float] = (frame_width / 2.0, frame_height / 2.0)
        self._target_switched_at: float = 0.0
        self._last_seen_at: float = 0.0
        self._entity_persistence: dict[str, float] = {}

    def reset(self) -> None:
        """Reset on scene cuts: treat new shot as a fresh camera composition."""
        self.composition.reset()
        self.speaker.reset()
        self._active_target_id = None
        self._active_target_center = (self.frame_width / 2.0, self.frame_height / 2.0)
        self._target_switched_at = 0.0
        self._last_seen_at = 0.0
        self._entity_persistence.clear()

    def set_audio_path(self, audio_path: str) -> None:
        self.speaker = SpeakerAnalyzer(audio_path)

    def _fits_in_crop(self, bbox: Sequence[float]) -> bool:
        w = bbox[2] - bbox[0]
        padding = self.crop_width * self.GROUP_PADDING_FRACTION
        return (w + padding) <= self.crop_width

    def _generate_candidates(
        self,
        entities: Sequence[DetectedEntity],
        now: float,
    ) -> list[TargetCandidate]:
        candidates: list[TargetCandidate] = []

        faces = [e for e in entities if e.category == "face"]
        persons = [e for e in entities if e.category == "person"]
        objects = [e for e in entities if e.category == "object"]

        # Track persistence of persons and prominent objects across frames
        for e in entities:
            # Hash position into a coarse spatial bucket to track presence
            bucket_x = int(((e.bbox[0] + e.bbox[2]) / 2.0) / (self.frame_width * 0.15))
            key = f"{e.category}_{bucket_x}"
            prev_time = self._entity_persistence.get(key, now)
            duration = min(5.0, (now - prev_time) + 0.1) if (now - prev_time < 0.5) else 0.1
            self._entity_persistence[key] = now

        # --- 1. TWO-PERSON OR MULTI-PERSON GROUP ---
        # If two people fit within the 9:16 crop window: KEEP BOTH!
        people_subjects = persons if persons else faces
        if len(people_subjects) >= 2:
            sorted_people = sorted(people_subjects, key=lambda p: (p.bbox[0] + p.bbox[2]) / 2.0)
            gx1 = min(p.bbox[0] for p in sorted_people[:2])
            gy1 = min(p.bbox[1] for p in sorted_people[:2])
            gx2 = max(p.bbox[2] for p in sorted_people[:2])
            gy2 = max(p.bbox[3] for p in sorted_people[:2])

            group_bbox = [gx1, gy1, gx2, gy2]
            if self._fits_in_crop(group_bbox):
                candidates.append(
                    TargetCandidate(
                        id="group_two_people",
                        target_type="group",
                        bbox=group_bbox,
                        cx=(gx1 + gx2) / 2.0,
                        cy=(gy1 + gy2) / 2.0,
                        entities=list(sorted_people[:2]),
                    )
                )

        # --- 2. PERSON + OBJECT / PROP COMPOSITE ---
        # If a person is holding/interacting with an object (food, money, phone, package, prize)
        for p_idx, p in enumerate(people_subjects):
            for o_idx, obj in enumerate(objects):
                # Check spatial adjacency or overlap between person and object
                px1, py1, px2, py2 = p.bbox
                ox1, oy1, ox2, oy2 = obj.bbox

                # Proximity: object is inside or within 15% frame width of the person
                margin_x = self.frame_width * 0.15
                margin_y = self.frame_height * 0.20
                if (ox2 >= px1 - margin_x and ox1 <= px2 + margin_x and
                    oy2 >= py1 - margin_y and oy1 <= py2 + margin_y):
                    cx1 = min(px1, ox1)
                    cy1 = min(py1, oy1)
                    cx2 = max(px2, ox2)
                    cy2 = max(py2, oy2)
                    comp_bbox = [cx1, cy1, cx2, cy2]
                    if self._fits_in_crop(comp_bbox):
                        candidates.append(
                            TargetCandidate(
                                id=f"composite_p{p_idx}_o{o_idx}",
                                target_type="person_object",
                                bbox=comp_bbox,
                                cx=(cx1 + cx2) / 2.0,
                                cy=(cy1 + cy2) / 2.0,
                                entities=[p, obj],
                            )
                        )

        # --- 3. INDIVIDUAL PERSONS & FACES ---
        for idx, p in enumerate(persons):
            cx = (p.bbox[0] + p.bbox[2]) / 2.0
            cy = (p.bbox[1] + p.bbox[3]) / 2.0
            candidates.append(
                TargetCandidate(
                    id=f"person_{idx}",
                    target_type="person",
                    bbox=p.bbox,
                    cx=cx,
                    cy=cy,
                    entities=[p],
                )
            )

        for idx, f in enumerate(faces):
            # If face is already inside an existing person candidate, don't duplicate
            cx = (f.bbox[0] + f.bbox[2]) / 2.0
            cy = (f.bbox[1] + f.bbox[3]) / 2.0
            candidates.append(
                TargetCandidate(
                    id=f"face_{idx}",
                    target_type="face",
                    bbox=f.bbox,
                    cx=cx,
                    cy=cy,
                    entities=[f],
                )
            )

        # --- 4. OBJECTS / PROPS (FOOD, MONEY, PRIZES, PHONE, ETC.) ---
        for idx, obj in enumerate(objects):
            cx = (obj.bbox[0] + obj.bbox[2]) / 2.0
            cy = (obj.bbox[1] + obj.bbox[3]) / 2.0
            candidates.append(
                TargetCandidate(
                    id=f"object_{obj.label}_{idx}",
                    target_type="object",
                    bbox=obj.bbox,
                    cx=cx,
                    cy=cy,
                    entities=[obj],
                )
            )

        # --- 5. FRAME CENTER FALLBACK ---
        candidates.append(
            TargetCandidate(
                id="frame_center",
                target_type="center",
                bbox=[0, 0, self.frame_width, self.frame_height],
                cx=self.frame_width / 2.0,
                cy=self.frame_height / 2.0,
            )
        )

        return candidates

    def _score_candidate(
        self,
        candidate: TargetCandidate,
        frame_bgr: np.ndarray,
        speaker_cues: list[SpeakerCue],
        salience_map: np.ndarray,
        now: float,
    ) -> float:
        # 1. ORIGINAL CAMERA FOCUS
        # Evaluates what the original camera is intentionally framing
        framing_score = self.composition.score_framing(candidate.bbox)
        size_score = self.composition.score_size(candidate.bbox)
        pan_alignment = self.composition.score_pan_alignment(candidate.bbox)

        # Persistence in the original shot
        bucket_x = int(candidate.cx / (self.frame_width * 0.15))
        key = f"{candidate.target_type}_{bucket_x}"
        persistence_val = min(1.0, self._entity_persistence.get(key, 0.0) / 3.0)

        original_camera_focus = (
            0.40 * framing_score +
            0.35 * size_score +
            0.15 * pan_alignment +
            0.10 * persistence_val
        )
        candidate.original_focus_score = original_camera_focus

        # 2. OBJECT / ACTION RELEVANCE
        # High score for food, money, challenges, prizes, and items held by subjects
        action_relevance = 0.0
        if candidate.target_type == "person_object":
            # Person interacting with food/money/prop is the gold standard viral shot
            action_relevance = 0.90
        elif candidate.target_type == "object":
            label = candidate.entities[0].label if candidate.entities else ""
            if label in ("food", "prop", "money_prop", "cell phone"):
                action_relevance = 0.85
            else:
                action_relevance = 0.60
        elif candidate.target_type == "group":
            action_relevance = 0.70  # Multi-person interaction / reaction
        candidate.action_score = action_relevance

        # 3. SPEAKER RELEVANCE
        # Does this candidate contain the active speaker?
        speaker_relevance = 0.0
        if candidate.target_type in ("face", "person", "group", "person_object"):
            # Check speaker cues for faces belonging to this candidate
            for cue in speaker_cues:
                if cue.speaker_score > speaker_relevance:
                    speaker_relevance = cue.speaker_score
        candidate.speaker_score = speaker_relevance

        # 4. VISUAL SALIENCE
        # Contrast / detail density inside candidate 9:16 crop window
        crop_left = int(max(0, min(self.frame_width - self.crop_width, candidate.cx - self.crop_width / 2.0)))
        crop_top = int(max(0, min(self.frame_height - self.crop_height, candidate.cy - self.crop_height / 2.0)))
        salience_score = self.composition.score_salience(
            salience_map, crop_left, crop_top, self.crop_width, self.crop_height
        )
        candidate.salience_score = salience_score

        # 5. MULTI-PERSON GROUP BONUS
        # If two people both fit in 9:16, give strong incentive to keep both
        both_fit_bonus = 0.55 if candidate.target_type == "group" else 0.0

        # 6. TEMPORAL CONSISTENCY & INCUMBENT BONUS
        incumbent_bonus = 0.0
        if self._active_target_id is not None:
            if candidate.id == self._active_target_id or candidate.id.startswith(self._active_target_id.split("_")[0]):
                incumbent_bonus = 0.35
                # If camera is actively panning away from the incumbent, decay the incumbent bonus
                if pan_alignment < -0.1:
                    incumbent_bonus *= max(0.0, 1.0 + pan_alignment)

        # 7. CAMERA PAN INTENT BONUS
        # If original camera is panning towards this candidate, give direct operator intent boost
        pan_intent_bonus = max(0.0, 0.45 * pan_alignment)

        # 8. PENALTIES
        # Jitter penalty: penalize distance from current camera position
        dist = math.hypot(candidate.cx - self._active_target_center[0], candidate.cy - self._active_target_center[1])
        jitter_penalty = min(0.35, (dist / float(self.frame_width)) * 0.40)

        # Crop penalty: penalize if key entity boundaries are cut off by 9:16 edges
        crop_right = crop_left + self.crop_width
        crop_penalty = 0.0
        if candidate.bbox[0] < crop_left or candidate.bbox[2] > crop_right:
            overflow = max(0.0, crop_left - candidate.bbox[0]) + max(0.0, candidate.bbox[2] - crop_right)
            crop_penalty = min(0.80, (overflow / float(self.crop_width)) * 1.5)

        # Center fallback penalty
        if candidate.target_type == "center":
            return 0.10

        # TOTAL SCORE FORMULA
        # SPEAKER != VISUAL SUBJECT: Original camera focus & action relevance have high weight.
        # Speaking increases score, but cannot easily overpower high visual focus + action.
        total_score = (
            0.35 * original_camera_focus
            + 0.30 * action_relevance
            + 0.25 * speaker_relevance
            + 0.15 * salience_score
            + both_fit_bonus
            + incumbent_bonus
            + pan_intent_bonus
            - crop_penalty
            - jitter_penalty
        )

        candidate.score = total_score
        return total_score

    def update(
        self,
        frame_bgr: np.ndarray,
        entities: Sequence[DetectedEntity],
        now: float,
    ) -> tuple[float, float]:
        """Main update loop per frame. Returns optimal 9:16 target center (cx, cy)."""
        # 1. Update camera motion from optical flow (if non-empty frame)
        if frame_bgr is not None and np.any(frame_bgr):
            self.composition.update_frame(frame_bgr)

        # 2. Extract visual salience map
        salience_map = self.composition.compute_salience_map(frame_bgr)

        # 3. Compute active speaker cues from faces
        faces = [e for e in entities if e.category == "face"]
        face_bboxes = [f.bbox for f in faces]
        speaker_cues = self.speaker.score_speaker(frame_bgr, face_bboxes, now)

        # 4. Generate all candidate crop targets
        candidates = self._generate_candidates(entities, now)

        # 5. Score every candidate
        for c in candidates:
            self._score_candidate(c, frame_bgr, speaker_cues, salience_map, now)

        # Find best candidate
        best = max(candidates, key=lambda c: c.score)

        # 6. Hysteresis & Minimum Dwell Time
        time_since_switch = now - self._target_switched_at
        if self._active_target_id is None:
            # First frame of scene / fresh initialization
            self._active_target_id = best.id
            self._active_target_center = (best.cx, best.cy)
            self._target_switched_at = now
            self._last_seen_at = now
            return self._active_target_center

        # If best candidate is the current incumbent, stick with it
        incumbent = next((c for c in candidates if c.id == self._active_target_id), None)
        if incumbent is not None:
            self._active_target_center = (incumbent.cx, incumbent.cy)
            self._last_seen_at = now

        # Only switch away from incumbent if:
        # 1) Minimum dwell time has passed (to avoid rapid ping-ponging)
        # 2) The new best target score beats incumbent by at least SWITCH_MARGIN
        # (or incumbent completely disappeared and hold_seconds expired)
        if best.id != self._active_target_id:
            can_switch = (time_since_switch >= self.MIN_DWELL_SECONDS)
            is_decisive = (incumbent is None) or (best.score >= incumbent.score * (1.0 + self.SWITCH_MARGIN))

            if can_switch and is_decisive:
                self._active_target_id = best.id
                self._active_target_center = (best.cx, best.cy)
                self._target_switched_at = now
                self._last_seen_at = now

        # Hold position if subjects temporarily dropped out
        if not entities and (now - self._last_seen_at > self.hold_seconds):
            self._active_target_center = (self.frame_width / 2.0, self.frame_height / 2.0)
            self._active_target_id = "frame_center"

        return self._active_target_center
