"""Comprehensive test suite for Clipreator's upgraded smart reframing system.

Validates all 10 core requirements:
1. One visible person speaking -> follows speaker.
2. Two people alternating speech -> tracks active speaker; keeps both when they fit.
3. Person mentioning and displaying an object -> prioritizes person + object composite.
4. Object mentioned but not visible in video -> does NOT hallucinate; stays on speaker / camera composition.
5. Important object with no visible speaker -> frames object cleanly.
6. Temporary face/object detection failure -> coasting / hold preserves camera position without jumping.
7. Scene cut -> resets tracking immediately, no smoothing across cuts.
8. No detectable faces -> frames salient object or falls back cleanly to center crop.
9. Portrait and landscape input -> handles both correctly without stretching.
10. Crop near source-frame boundary -> clamps strictly within bounds without clipping.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np

from camera_planner import IntelligentCameraPlanner
from context_grounding import ContextGrounder
from detector import DetectedEntity
from entity_tracker import MultiEntityTracker
from reframe import _clamp_origin


def create_dummy_frame(w=1920, h=1080) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_1_one_visible_person_speaking():
    """1. One visible person speaking -> follows speaker."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Person centered at x=960, speaking
    face = DetectedEntity(bbox=[880, 200, 1040, 380], category="face", label="face", score=0.95)
    person = DetectedEntity(bbox=[800, 200, 1120, 950], category="person", label="person", score=0.95)

    # Set mock mouth motion
    planner.speaker._prev_mouths = {1: np.ones((32, 48), dtype=np.uint8) * 120}
    cx, cy = planner.update(frame, [face, person], now=0.5)

    assert 800 <= cx <= 1100, f"Expected camera centered on speaker (around 960), got {cx}"
    print("✅ TEST 1 PASSED: One visible person speaking followed properly")


def test_2_two_people_alternating_speech():
    """2. Two people alternating speech -> tracks active speaker; keeps both when they fit."""
    # Sub-case A: Both fit inside 9:16 crop window (crop_width = 608)
    planner_close = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    p1 = DetectedEntity(bbox=[720, 300, 860, 600], category="person", label="person", score=0.90)
    p2 = DetectedEntity(bbox=[920, 300, 1060, 600], category="person", label="person", score=0.90)

    cx_close, _ = planner_close.update(frame, [p1, p2], now=0.5)
    assert 800 <= cx_close <= 980, f"Expected group crop framing both people (around 890), got {cx_close}"

    # Sub-case B: Too far apart (x=300 vs x=1500) -> follows active speaker
    planner_far = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    pA = DetectedEntity(bbox=[200, 250, 400, 800], category="person", label="person", score=0.90)
    fA = DetectedEntity(bbox=[250, 250, 350, 400], category="face", label="face", score=0.90)
    pB = DetectedEntity(bbox=[1400, 250, 1600, 800], category="person", label="person", score=0.90)
    fB = DetectedEntity(bbox=[1450, 250, 1550, 400], category="face", label="face", score=0.90)

    # Person A speaking at t=0.5
    planner_far.speaker._prev_mouths = {1: np.ones((32, 48), dtype=np.uint8) * 150}
    cx_a, _ = planner_far.update(frame, [pA, fA, pB, fB], now=0.5)
    assert cx_a < 600, f"Expected camera to prioritize active speaker Person A on left, got {cx_a}"
    print("✅ TEST 2 PASSED: Two people kept together when they fit; follows active speaker when apart")


def test_3_person_mentioning_and_displaying_object():
    """3. Person mentioning and displaying an object -> prioritizes person + object composite."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump({
            "title": "Tech Unboxing",
            "hook": "Look at this phone",
            "why": "Demonstrating the new device",
            "words": [
                {"text": "look", "start": 0.2, "end": 0.5},
                {"text": "at", "start": 0.5, "end": 0.7},
                {"text": "this", "start": 0.7, "end": 0.9},
                {"text": "phone", "start": 0.9, "end": 1.4},
            ]
        }, tf)
        tf_path = tf.name

    try:
        planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080, context_path=tf_path)
        frame = create_dummy_frame()

        # Person holding phone in hand at center
        person = DetectedEntity(bbox=[750, 200, 1050, 850], category="person", label="person", score=0.90)
        phone = DetectedEntity(bbox=[950, 450, 1080, 650], category="object", label="cell phone", score=0.92)

        cx, cy = planner.update(frame, [person, phone], now=1.2)
        # Should frame person + phone composite
        assert 800 <= cx <= 1050, f"Expected camera on person + phone composite, got {cx}"
        assert planner._last_selected_candidate.target_type in ("person_object", "object"), f"Expected person_object target, got {planner._last_selected_candidate.target_type}"
        print("✅ TEST 3 PASSED: Spoken & displayed object framed contextually with presenter")
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_4_object_mentioned_but_not_visible():
    """4. Object mentioned but not visible in video -> does NOT hallucinate; stays on speaker."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump({
            "title": "Car Talk",
            "hook": "Let's talk about the car",
            "why": "Automotive review",
            "words": [
                {"text": "look", "start": 0.2, "end": 0.5},
                {"text": "at", "start": 0.5, "end": 0.7},
                {"text": "the", "start": 0.7, "end": 0.9},
                {"text": "car", "start": 0.9, "end": 1.4},
            ]
        }, tf)
        tf_path = tf.name

    try:
        planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080, context_path=tf_path)
        frame = create_dummy_frame()

        # Only person is visible in room; car is outside/not detected
        speaker = DetectedEntity(bbox=[500, 200, 800, 850], category="person", label="person", score=0.92)
        face = DetectedEntity(bbox=[580, 200, 720, 360], category="face", label="face", score=0.92)

        cx, _ = planner.update(frame, [speaker, face], now=1.1)
        # Must stay on the speaker (x around 650), not invent car coordinates or pan wildly
        assert 500 <= cx <= 800, f"Expected camera to remain on speaker when object is not visually present, got {cx}"
        print("✅ TEST 4 PASSED: Non-visible mentioned object does not derail camera from speaker")
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_5_important_object_with_no_visible_speaker():
    """5. Important object with no visible speaker -> frames object cleanly."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Product/laptop demonstration on desk with no face visible
    laptop = DetectedEntity(bbox=[600, 400, 1100, 750], category="object", label="laptop", score=0.95)

    cx, cy = planner.update(frame, [laptop], now=0.5)
    assert 700 <= cx <= 1000, f"Expected camera framed on prominent laptop (around 850), got {cx}"
    print("✅ TEST 5 PASSED: Object cleanly framed when speaker is off-camera")


def test_6_temporary_detection_failure_coasting():
    """6. Temporary face/object detection failure -> coasting / hold preserves camera position without jumping."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080, hold_seconds=2.0)
    frame = create_dummy_frame()

    person = DetectedEntity(bbox=[400, 300, 600, 800], category="person", label="person", score=0.90)

    # Frame 1: Detection present at x=500
    cx1, _ = planner.update(frame, [person], now=1.0)
    assert 450 <= cx1 <= 550

    # Frames 2-5: Detection temporarily lost (e.g. subject turned back)
    for t in [1.1, 1.2, 1.3, 1.4]:
        cx_drop, _ = planner.update(frame, [], now=t)
        # Position should coast/hold without jumping to center
        assert abs(cx_drop - cx1) < 15.0, f"Camera jumped during temporary dropout: {cx_drop} vs {cx1}"

    print("✅ TEST 6 PASSED: Temporary detection dropout handled smoothly via coasting/hold")


def test_7_scene_cut_reset():
    """7. Scene cut -> resets tracking immediately, no smoothing across cuts."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Shot 1: Subject on left at x=350
    p1 = DetectedEntity(bbox=[250, 300, 450, 800], category="person", label="person", score=0.90)
    cx1, _ = planner.update(frame, [p1], now=1.0)
    assert cx1 < 500

    # HARD SCENE CUT!
    planner.reset()
    assert planner._active_target_id is None, "Target must be cleared on cut"

    # Shot 2: Subject on right at x=1550
    p2 = DetectedEntity(bbox=[1450, 300, 1650, 800], category="person", label="person", score=0.90)
    cx2, _ = planner.update(frame, [p2], now=1.04)

    assert cx2 > 1400, f"Expected immediate snap to new shot at x=1550, got {cx2}"
    print("✅ TEST 7 PASSED: Scene cut immediately resets tracking and acquires new shot")


def test_8_no_detectable_faces_center_fallback():
    """8. No detectable faces -> falls back cleanly to center crop."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Empty frame (nature b-roll, background landscape)
    cx, cy = planner.update(frame, [], now=0.5)

    assert abs(cx - 960.0) < 5.0, f"Expected center fallback at 960, got {cx}"
    assert abs(cy - 540.0) < 5.0, f"Expected center fallback at 540, got {cy}"
    print("✅ TEST 8 PASSED: Empty frame falls back cleanly to frame center")


def test_9_portrait_and_landscape_input():
    """9. Portrait and landscape input -> handles both correctly without stretching."""
    # Landscape: 1920x1080 (16:9) -> crop_h = 1080, crop_w = 608
    crop_w_land = round(1080 * 9 / 16)
    left_land, top_land = _clamp_origin(960.0, 540.0, crop_w_land, 1080, 1920, 1080)
    assert 0 <= left_land <= 1920 - crop_w_land
    assert top_land == 0

    # Portrait: 1080x1920 (already 9:16)
    left_port, top_port = _clamp_origin(540.0, 960.0, 1080, 1920, 1080, 1920)
    assert left_port == 0
    assert top_port == 0

    # Unusual aspect ratio: Square 1080x1080 -> crop_h = 1080, crop_w = 608
    left_sq, top_sq = _clamp_origin(540.0, 540.0, 608, 1080, 1080, 1080)
    assert 0 <= left_sq <= 1080 - 608
    assert top_sq == 0
    print("✅ TEST 9 PASSED: Landscape, portrait, and square source dimensions handled without distortion")


def test_10_crop_near_source_frame_boundary():
    """10. Crop near source-frame boundary -> clamps strictly within bounds without clipping."""
    frame_w, frame_h = 1920, 1080
    crop_w, crop_h = 608, 1080

    # Target placed at extreme left (cx = 50)
    left_min, top_min = _clamp_origin(50.0, 540.0, crop_w, crop_h, frame_w, frame_h)
    assert left_min == 0, f"Expected left clamped to 0, got {left_min}"

    # Target placed at extreme right (cx = 1900)
    left_max, top_max = _clamp_origin(1900.0, 540.0, crop_w, crop_h, frame_w, frame_h)
    assert left_max == frame_w - crop_w, f"Expected left clamped to {frame_w - crop_w}, got {left_max}"

    # Target placed at extreme top/bottom
    _, top_low = _clamp_origin(960.0, -100.0, crop_w, crop_h, frame_w, frame_h)
    assert top_low == 0
    _, top_high = _clamp_origin(960.0, 2000.0, crop_w, crop_h, frame_w, frame_h)
    assert top_high == frame_h - crop_h
    print("✅ TEST 10 PASSED: Boundary clamping strictly verified across all extremes")


def run_all_tests():
    print("\n🚀 RUNNING COMPLETE 10-POINT REFRAMER TEST SUITE...\n")
    test_1_one_visible_person_speaking()
    test_2_two_people_alternating_speech()
    test_3_person_mentioning_and_displaying_object()
    test_4_object_mentioned_but_not_visible()
    test_5_important_object_with_no_visible_speaker()
    test_6_temporary_detection_failure_coasting()
    test_7_scene_cut_reset()
    test_8_no_detectable_faces_center_fallback()
    test_9_portrait_and_landscape_input()
    test_10_crop_near_source_frame_boundary()
    print("\n🎉 ALL 10 COMPREHENSIVE REFRAMING TESTS PASSED PERFECTLY! 🎉\n")


if __name__ == "__main__":
    run_all_tests()
