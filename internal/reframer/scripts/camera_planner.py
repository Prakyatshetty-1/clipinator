"""Intelligent Camera Planner for Clipreator 9:16 Reframing.

Evaluates multi-modal visual targets with context-aware scoring:
1. Active speaker cues (faster-whisper voice intervals + tracked mouth motion)
2. Spoken and demonstrated objects (grounded in transcript words + YOLO detections)
3. Person + Object composites (showing speaker and product together)
4. Multi-person groups (framing both when they fit inside 9:16)
5. Original camera operator intent (framing, prominence, optical flow pan alignment)
6. Hysteresis, dwell-time locking, and scene-cut resets to eliminate jitter and ping-ponging
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from composition import CompositionAnalyzer
from context_grounding import ContextGrounder
from detector import DetectedEntity
from entity_tracker import MultiEntityTracker, TrackedEntity
from speaker import SpeakerAnalyzer, SpeakerCue


@dataclass
class ScoringWeights:
    speaker: float = 0.35
    transcript_object: float = 0.35
    interaction: float = 0.25
    camera_focus: float = 0.25
    salience: float = 0.15
    group_bonus: float = 0.50
    incumbent_bonus: float = 0.35
    pan_intent_bonus: float = 0.40
    crop_penalty: float = 1.20
    switch_penalty: float = 0.30


@dataclass
class TargetCandidate:
    id: str
    target_type: str  # 'group', 'person_object', 'person', 'face', 'object', 'center'
    bbox: list[float]  # [x1, y1, x2, y2]
    cx: float
    cy: float
    entities: list[any] = field(default_factory=list)
    score: float = 0.0
    speaker_score: float = 0.0
    object_relevance: float = 0.0
    original_focus_score: float = 0.0
    action_score: float = 0.0
    salience_score: float = 0.0
    reason: str = ""


class IntelligentCameraPlanner:
    SWITCH_MARGIN = 0.28          # New target must beat incumbent by 28% to trigger voluntary switch
    MIN_DWELL_SECONDS = 1.25      # Camera stays on a target for at least 1.25s before voluntary switch
    GROUP_PADDING_FRACTION = 0.12 # Edge padding for group crop
    HEADROOM_FRACTION = 0.42      # Vertical headroom placement

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        crop_height: int,
        hold_seconds: float = 2.0,
        weights: ScoringWeights | None = None,
        context_path: str | Path | None = None,
    ) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.crop_width = crop_width
        self.crop_height = crop_height
        self.hold_seconds = hold_seconds
        self.weights = weights or ScoringWeights()

        self.composition = CompositionAnalyzer(frame_width, frame_height)
        self.speaker = SpeakerAnalyzer(context_path=context_path)
        self.grounder = ContextGrounder(context_path=context_path)
        self.tracker = MultiEntityTracker(frame_width, frame_height)

        self._active_target_id: str | None = None
        self._active_target_center: tuple[float, float] = (frame_width / 2.0, frame_height / 2.0)
        self._target_switched_at: float = 0.0
        self._last_seen_at: float = 0.0
        self._last_selected_candidate: TargetCandidate | None = None
        self._debug_logs: list[dict] = []

    def reset(self) -> None:
        """Reset on scene cuts: treat new shot as a fresh camera composition."""
        self.composition.reset()
        self.speaker.reset()
        self.tracker.reset()
        self._active_target_id = None
        self._active_target_center = (self.frame_width / 2.0, self.frame_height / 2.0)
        self._target_switched_at = 0.0
        self._last_seen_at = 0.0
        self._last_selected_candidate = None

    def set_audio_path(self, audio_path: str) -> None:
        self.speaker._load_audio(audio_path)

    def set_context_path(self, context_path: str | Path) -> None:
        self.grounder.load_context(context_path)
        self.speaker.load_context(context_path)

    def _fits_in_crop(self, bbox: Sequence[float]) -> bool:
        w = bbox[2] - bbox[0]
        padding = self.crop_width * self.GROUP_PADDING_FRACTION
        return (w + padding) <= self.crop_width

    def _generate_candidates(
        self,
        tracks: Sequence[TrackedEntity],
        now: float,
    ) -> list[TargetCandidate]:
        candidates: list[TargetCandidate] = []

        faces = [t for t in tracks if t.category == "face"]
        persons = [t for t in tracks if t.category == "person"]
        objects = [t for t in tracks if t.category == "object"]

        # --- 1. TWO-PERSON GROUP ---
        # If two people fit within the 9:16 crop window: KEEP BOTH!
        people_subjects = persons if persons else faces
        if len(people_subjects) >= 2:
            sorted_people = sorted(people_subjects, key=lambda p: p.cx)
            for i in range(len(sorted_people) - 1):
                p1, p2 = sorted_people[i], sorted_people[i + 1]
                gx1 = min(p1.bbox[0], p2.bbox[0])
                gy1 = min(p1.bbox[1], p2.bbox[1])
                gx2 = max(p1.bbox[2], p2.bbox[2])
                gy2 = max(p1.bbox[3], p2.bbox[3])
                group_bbox = [gx1, gy1, gx2, gy2]

                if self._fits_in_crop(group_bbox):
                    candidates.append(
                        TargetCandidate(
                            id=f"group_t{p1.track_id}_t{p2.track_id}",
                            target_type="group",
                            bbox=group_bbox,
                            cx=(gx1 + gx2) / 2.0,
                            cy=(gy1 + gy2) / 2.0,
                            entities=[p1, p2],
                            reason="2-person group within 9:16 crop",
                        )
                    )
                    break

        # --- 2. PERSON + OBJECT / PROP COMPOSITE ---
        # If a person is holding/interacting with an object (food, money, phone, laptop, package)
        for p in people_subjects:
            for obj in objects:
                px1, py1, px2, py2 = p.bbox
                ox1, oy1, ox2, oy2 = obj.bbox

                margin_x = self.frame_width * 0.16
                margin_y = self.frame_height * 0.22
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
                                id=f"composite_p{p.track_id}_o{obj.track_id}",
                                target_type="person_object",
                                bbox=comp_bbox,
                                cx=(cx1 + cx2) / 2.0,
                                cy=(cy1 + cy2) / 2.0,
                                entities=[p, obj],
                                reason=f"person holding/interacting with {obj.label}",
                            )
                        )

        # --- 3. INDIVIDUAL PERSONS ---
        for p in persons:
            candidates.append(
                TargetCandidate(
                    id=f"person_t{p.track_id}",
                    target_type="person",
                    bbox=p.bbox,
                    cx=p.cx,
                    cy=p.cy,
                    entities=[p],
                    reason=f"person #{p.track_id}",
                )
            )

        # --- 4. INDIVIDUAL FACES ---
        for f in faces:
            # Check if this face is already enclosed in a person candidate
            enclosed = False
            for p in persons:
                if (f.bbox[0] >= p.bbox[0] - 20 and f.bbox[2] <= p.bbox[2] + 20 and
                    f.bbox[1] >= p.bbox[1] - 20 and f.bbox[3] <= p.bbox[3] + 40):
                    enclosed = True
                    break
            if not enclosed:
                candidates.append(
                    TargetCandidate(
                        id=f"face_t{f.track_id}",
                        target_type="face",
                        bbox=f.bbox,
                        cx=f.cx,
                        cy=f.cy,
                        entities=[f],
                        reason=f"face #{f.track_id}",
                    )
                )

        # --- 5. GROUNDED OBJECTS / PROPS ---
        for obj in objects:
            candidates.append(
                TargetCandidate(
                    id=f"object_{obj.label}_t{obj.track_id}",
                    target_type="object",
                    bbox=obj.bbox,
                    cx=obj.cx,
                    cy=obj.cy,
                    entities=[obj],
                    reason=f"detected {obj.label} #{obj.track_id}",
                )
            )

        # --- 6. FRAME CENTER FALLBACK ---
        candidates.append(
            TargetCandidate(
                id="frame_center",
                target_type="center",
                bbox=[0, 0, self.frame_width, self.frame_height],
                cx=self.frame_width / 2.0,
                cy=self.frame_height / 2.0,
                reason="frame center fallback",
            )
        )

        return candidates

    def _score_candidate(
        self,
        candidate: TargetCandidate,
        speaker_cues: list[SpeakerCue],
        salience_map: np.ndarray,
        all_tracks: Sequence[TrackedEntity],
        now: float,
    ) -> float:
        w = self.weights

        # 1. ORIGINAL CAMERA FOCUS
        framing_score = self.composition.score_framing(candidate.bbox)
        size_score = self.composition.score_size(candidate.bbox)
        pan_alignment = self.composition.score_pan_alignment(candidate.bbox)

        original_camera_focus = (
            0.40 * framing_score +
            0.35 * size_score +
            0.25 * max(0.0, pan_alignment)
        )
        candidate.original_focus_score = original_camera_focus

        # 2. ACTIVE SPEAKER RELEVANCE
        speaker_relevance = 0.0
        candidate_track_ids = {getattr(e, "track_id", -1) for e in candidate.entities}
        if candidate.target_type in ("person", "person_object"):
            for p_entity in candidate.entities:
                if getattr(p_entity, "category", "") == "person":
                    px1, py1, px2, py2 = p_entity.bbox
                    for t in all_tracks:
                        if t.category == "face":
                            fx1, fy1, fx2, fy2 = t.bbox
                            if fx1 >= px1 - 30 and fx2 <= px2 + 30 and fy1 >= py1 - 30 and fy2 <= py2 + 50:
                                candidate_track_ids.add(t.track_id)
        for cue in speaker_cues:
            cue_person_id = getattr(cue, "person_track_id", None)
            if cue.track_id in candidate_track_ids or (cue_person_id is not None and cue_person_id in candidate_track_ids) or candidate.target_type == "group":
                if cue.speaker_score > speaker_relevance:
                    speaker_relevance = cue.speaker_score
        candidate.speaker_score = speaker_relevance

        # 3. CONTEXT & SPOKEN OBJECT RELEVANCE
        object_relevance = 0.0
        person_boxes = [t.bbox for t in all_tracks if t.category == "person"]

        if candidate.target_type == "object":
            obj = candidate.entities[0]
            object_relevance = self.grounder.evaluate_object_relevance(
                obj.bbox, obj.label, now, person_boxes
            )
        elif candidate.target_type == "person_object":
            # Person with grounded object
            obj = candidate.entities[1]
            base_rel = self.grounder.evaluate_object_relevance(
                obj.bbox, obj.label, now, person_boxes
            )
            object_relevance = max(base_rel, 0.75)  # Demonstrations get high action baseline
        elif candidate.target_type == "group":
            object_relevance = 0.35  # Group dialogue baseline
        candidate.object_relevance = object_relevance

        # 4. ACTION / INTERACTION RELEVANCE
        action_relevance = 0.0
        if candidate.target_type == "person_object":
            action_relevance = 0.85
        elif candidate.target_type == "group":
            action_relevance = 0.70
        elif candidate.target_type == "object":
            action_relevance = 0.60
        candidate.action_score = action_relevance

        # 5. VISUAL SALIENCE DENSITY
        crop_left = int(max(0, min(self.frame_width - self.crop_width, candidate.cx - self.crop_width / 2.0)))
        crop_top = int(max(0, min(self.frame_height - self.crop_height, candidate.cy - self.crop_height / 2.0)))
        salience_score = self.composition.score_salience(
            salience_map, crop_left, crop_top, self.crop_width, self.crop_height
        )
        candidate.salience_score = salience_score

        # 6. BONUSES
        both_fit_bonus = w.group_bonus if candidate.target_type == "group" else 0.0

        incumbent_bonus = 0.0
        if self._active_target_id is not None:
            if candidate.id == self._active_target_id:
                incumbent_bonus = w.incumbent_bonus
                if pan_alignment < -0.15:
                    incumbent_bonus = 0.0

        pan_intent_bonus = max(0.0, w.pan_intent_bonus * pan_alignment)

        # 7. PENALTIES
        dist = math.hypot(candidate.cx - self._active_target_center[0], candidate.cy - self._active_target_center[1])
        jitter_penalty = min(0.35, (dist / float(self.frame_width)) * w.switch_penalty)
        if pan_alignment > 0.15:
            jitter_penalty *= max(0.0, 1.0 - pan_alignment)

        # Crop penalty: penalize if key entity boundaries are cut off by 9:16 edges
        crop_right = crop_left + self.crop_width
        crop_penalty = 0.0
        if candidate.bbox[0] < crop_left or candidate.bbox[2] > crop_right:
            overflow = max(0.0, crop_left - candidate.bbox[0]) + max(0.0, candidate.bbox[2] - crop_right)
            crop_penalty = min(0.80, (overflow / float(self.crop_width)) * w.crop_penalty)

        # Center fallback penalty
        if candidate.target_type == "center":
            candidate.score = 0.10
            return 0.10

        # TOTAL SCORE FORMULA
        total_score = (
            w.speaker * speaker_relevance
            + w.transcript_object * object_relevance
            + w.interaction * action_relevance
            + w.camera_focus * original_camera_focus
            + w.salience * salience_score
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
        # 1. Update camera motion from optical flow
        if frame_bgr is not None and frame_bgr.size > 0:
            self.composition.update_frame(frame_bgr)

        # 2. Visual salience map
        salience_map = self.composition.compute_salience_map(frame_bgr)

        # 3. Multi-Entity Tracking
        active_tracks = self.tracker.update(entities, now)

        # 4. Active Speaker Cues on Tracked Faces
        face_tracks = []
        for t in active_tracks:
            if t.category == "face":
                for p in active_tracks:
                    if p.category == "person":
                        if (t.bbox[0] >= p.bbox[0] - 30 and t.bbox[2] <= p.bbox[2] + 30 and
                            t.bbox[1] >= p.bbox[1] - 30 and t.bbox[3] <= p.bbox[3] + 50):
                            t.person_track_id = p.track_id
                            break
                face_tracks.append(t)
            elif t.category == "person":
                has_face = any(
                    f.category == "face" and
                    f.bbox[0] >= t.bbox[0] - 30 and f.bbox[2] <= t.bbox[2] + 30 and
                    f.bbox[1] >= t.bbox[1] - 30 and f.bbox[3] <= t.bbox[3] + 50
                    for f in active_tracks
                )
                if not has_face:
                    hx1, hy1, hx2, hy2 = t.bbox
                    head_bbox = [hx1 + (hx2 - hx1) * 0.25, hy1, hx2 - (hx2 - hx1) * 0.25, hy1 + (hy2 - hy1) * 0.35]
                    face_tracks.append(TrackedEntity(t.track_id, "face", "face", head_bbox, t.score, t.first_seen, t.last_seen))

        speaker_cues = self.speaker.score_speaker_tracks(frame_bgr, face_tracks, now)

        # 5. Generate Candidate Targets
        candidates = self._generate_candidates(active_tracks, now)

        # 6. Score All Candidates
        for c in candidates:
            self._score_candidate(c, speaker_cues, salience_map, active_tracks, now)

        best = max(candidates, key=lambda c: c.score)

        # 7. Dwell Time, Hysteresis, and Switch Decision
        time_since_switch = now - self._target_switched_at
        if self._active_target_id is None:
            self._active_target_id = best.id
            self._active_target_center = (best.cx, best.cy)
            self._target_switched_at = now
            self._last_seen_at = now
            self._last_selected_candidate = best
            return self._active_target_center

        incumbent = next((c for c in candidates if c.id == self._active_target_id), None)
        if incumbent is not None:
            self._active_target_center = (incumbent.cx, incumbent.cy)
            self._last_seen_at = now

        if best.id != self._active_target_id:
            can_switch = (time_since_switch >= self.MIN_DWELL_SECONDS)
            is_decisive = (incumbent is None) or (best.score >= incumbent.score * (1.0 + self.SWITCH_MARGIN))

            if can_switch and is_decisive:
                self._active_target_id = best.id
                self._active_target_center = (best.cx, best.cy)
                self._target_switched_at = now
                self._last_seen_at = now
                self._last_selected_candidate = best

        if not active_tracks and (now - self._last_seen_at > self.hold_seconds):
            self._active_target_center = (self.frame_width / 2.0, self.frame_height / 2.0)
            self._active_target_id = "frame_center"

        return self._active_target_center
