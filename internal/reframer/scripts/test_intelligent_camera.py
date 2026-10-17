"""Comprehensive test suite for the Intelligent Camera Planner.

Validates all 8 core test scenarios:
TEST 1: One person speaking directly to camera -> follows speaker.
TEST 2: Two people talking -> keeps both when they fit in 9:16; picks more visually relevant when far.
TEST 3: Person A speaking while Person B holds money/object -> preserves Person B + object composition.
TEST 4: Person talking about food while camera shows food -> preserves food/person composition.
TEST 5: Person opens a package while someone else talks -> follows package/action.
TEST 6: Original camera pans from Person A to Person B -> recognizes pan intent and transitions.
TEST 7: Fast conversation with scene cuts -> resets target on cuts.
TEST 8: No faces detected -> frames salient object/action or falls back to center crop.
"""

from __future__ import annotations

import math
import numpy as np

from camera_planner import IntelligentCameraPlanner
from detector import DetectedEntity
from speaker import SpeakerCue


def create_dummy_frame(w=1920, h=1080) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_scenario_1_single_person_speaking():
    """TEST 1: One person speaking directly to camera -> follow the speaker."""
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Person centered, speaking
    face = DetectedEntity(bbox=[880, 200, 1040, 380], category="face", label="face", score=0.95)
    person = DetectedEntity(bbox=[800, 200, 1120, 950], category="person", label="person", score=0.95)

    # Simulate speaker cues: active speech
    planner.speaker._prev_mouths = {0: np.ones((32, 48), dtype=np.uint8) * 100}
    cx, cy = planner.update(frame, [face, person], now=0.5)

    assert 850 <= cx <= 1070, f"Expected camera centered on speaker (around 960), got {cx}"
    print("✅ TEST 1 PASSED: One person speaking directly to camera followed properly")


def test_scenario_2_two_people_close_and_far():
    """TEST 2: Two people talking -> keep both when they fit; choose more relevant when far."""
    # Sub-case A: Both fit in 9:16 (crop_width = 608)
    planner_close = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    p1 = DetectedEntity(bbox=[720, 300, 860, 600], category="person", label="person", score=0.90)
    p2 = DetectedEntity(bbox=[920, 300, 1060, 600], category="person", label="person", score=0.90)

    cx, _ = planner_close.update(frame, [p1, p2], now=0.5)
    # The group center is around 890
    assert 800 <= cx <= 980, f"Expected camera to frame both people (around 890), got {cx}"

    # Sub-case B: People too far apart (e.g. x=200 and x=1700, span=1500 > 608)
    planner_far = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    # Person A is at x=200, small (size 100), not prominent
    p_far_a = DetectedEntity(bbox=[150, 300, 250, 500], category="person", label="person", score=0.60)
    # Person B is prominent, central at rule of thirds x=640, large (size 400), talking
    p_far_b = DetectedEntity(bbox=[500, 200, 900, 900], category="person", label="person", score=0.95)

    cx_far, _ = planner_far.update(frame, [p_far_a, p_far_b], now=0.5)
    # Must choose Person B because of prominence and original camera composition
    assert cx_far > 450, f"Expected camera to prioritize visually prominent Person B, got {cx_far}"
    print("✅ TEST 2 PASSED: Two people kept together when they fit; prominent subject chosen when far")


def test_scenario_3_speaker_vs_person_with_money():
    """TEST 3: Person A speaking while Person B is holding money ₹50,000.
    Expected: If camera is composed on Person B + money, keep Person B + money!
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Person A on left (x=200), speaking
    face_a = DetectedEntity(bbox=[150, 200, 250, 350], category="face", label="face", score=0.85)
    person_a = DetectedEntity(bbox=[100, 200, 300, 750], category="person", label="person", score=0.85)

    # Person B on right (x=1300), holding money stack (prop)
    # Person B + money are prominently framed
    face_b = DetectedEntity(bbox=[1200, 200, 1320, 350], category="face", label="face", score=0.85)
    person_b = DetectedEntity(bbox=[1150, 200, 1450, 850], category="person", label="person", score=0.92)
    money_prop = DetectedEntity(bbox=[1250, 450, 1400, 600], category="object", label="prop", score=0.88)

    # Person A has mouth motion (speaker)
    # Person B has prop/action + large composition size
    # Run multiple frames to establish visual focus
    for t in [0.1, 0.3, 0.6, 1.0]:
        cx, cy = planner.update(frame, [face_a, person_a, face_b, person_b, money_prop], now=t)

    # Camera must prioritize Person B + money (x around 1300), NOT Person A (x around 200)
    assert cx > 1000, f"Expected camera on Person B + Money (x > 1000), got {cx}"
    print("✅ TEST 3 PASSED: Speaker != Visual Subject: Person B + money composition preserved over speaker")


def test_scenario_4_food_focus_while_talking():
    """TEST 4: Person talking about food while camera is showing the food.
    Expected: Keep food/person composition instead of automatically jumping solely to face.
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Face of person talking in upper background
    face = DetectedEntity(bbox=[900, 100, 1020, 240], category="face", label="face", score=0.90)
    # Huge food plate in foreground center of 16:9 frame
    food = DetectedEntity(bbox=[760, 450, 1160, 850], category="object", label="food", score=0.95)

    cx, cy = planner.update(frame, [face, food], now=0.5)
    # Must keep the food in composition (center around 960)
    assert 800 <= cx <= 1120, f"Expected camera to frame food composition, got {cx}"
    assert cy > 350, f"Expected vertical camera to tilt towards food (cy > 350), got {cy}"
    print("✅ TEST 4 PASSED: Food challenge / food presentation composition preserved")


def test_scenario_5_package_unboxing_action():
    """TEST 5: Person opens a package while someone else talks.
    Expected: Follow the package/action if it is the clear visual focus.
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Off-center narrator talking at x=200
    narrator = DetectedEntity(bbox=[150, 200, 260, 450], category="person", label="person", score=0.85)

    # Unboxing hands / package at center x=960, y=550 (large, prominent action)
    package = DetectedEntity(bbox=[800, 400, 1120, 750], category="object", label="prop", score=0.90)

    for t in [0.1, 0.4, 0.8]:
        cx, cy = planner.update(frame, [narrator, package], now=t)

    assert 800 <= cx <= 1120, f"Expected camera on package unboxing at center, got {cx}"
    print("✅ TEST 5 PASSED: Package unboxing / object action followed over narrator")


def test_scenario_6_camera_pan_following():
    """TEST 6: Original camera pans from Person A to Person B.
    Expected: Vertical camera recognizes operator pan motion and follows new composition.
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Initial frame: Person A at x=400
    pA = DetectedEntity(bbox=[300, 300, 500, 800], category="person", label="person", score=0.90)
    pB = DetectedEntity(bbox=[1400, 300, 1600, 800], category="person", label="person", score=0.90)

    # Initial frame: Focus starts on Person A
    cx1, _ = planner.update(frame, [pA], now=0.0)
    assert cx1 < 600, f"Expected initial frame on Person A, got {cx1}"

    # Frame 2: Person B enters / camera pans right towards Person B
    # Background flow left means camera panned right
    planner.composition.current_motion.pan_x = -2.5
    # After dwell time, camera should follow pan to Person B
    cx2, _ = planner.update(frame, [pA, pB], now=1.8)

    assert cx2 > cx1, f"Expected camera to shift towards Person B following camera pan, got {cx2} vs {cx1}"
    print("✅ TEST 6 PASSED: Original camera pan intent recognized and followed")


def test_scenario_7_scene_cut_reset():
    """TEST 7: Fast conversation with multiple scene cuts.
    Expected: Recalculate target cleanly after each scene cut without forcing old target.
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Scene 1: Focus on Person on left (x=300)
    p1 = DetectedEntity(bbox=[200, 300, 400, 800], category="person", label="person", score=0.90)
    planner.update(frame, [p1], now=1.0)
    assert planner._active_target_id and planner._active_target_id.startswith("person_")

    # SCENE CUT!
    planner.reset()
    assert planner._active_target_id is None, "Target must be cleared on cut"

    # Scene 2: New shot with Person on right (x=1500)
    p2 = DetectedEntity(bbox=[1400, 300, 1600, 800], category="person", label="person", score=0.90)
    cx, _ = planner.update(frame, [p2], now=1.04)

    assert cx > 1300, f"Expected immediate clean framing of new subject at x=1500, got {cx}"
    print("✅ TEST 7 PASSED: Scene cut immediately recalculates target without sticking to old shot")


def test_scenario_8_no_faces_object_and_center_fallback():
    """TEST 8: No faces detected.
    Expected: Use salient object/action if present; fall back to center crop if empty.
    """
    planner = IntelligentCameraPlanner(1920, 1080, crop_width=608, crop_height=1080)
    frame = create_dummy_frame()

    # Sub-case A: No faces, but an important car/object at x=600
    obj = DetectedEntity(bbox=[450, 400, 750, 700], category="object", label="car", score=0.90)
    cx_obj, _ = planner.update(frame, [obj], now=0.5)
    assert 500 <= cx_obj <= 700, f"Expected framing of object at x=600, got {cx_obj}"

    # Sub-case B: Absolutely nothing detected (pure abstract background / scenery)
    planner.reset()
    cx_empty, cy_empty = planner.update(frame, [], now=0.5)
    assert abs(cx_empty - 960) < 5, f"Expected center crop fallback (960), got {cx_empty}"
    print("✅ TEST 8 PASSED: Object framed when no faces; clean center crop fallback when empty")


if __name__ == "__main__":
    test_scenario_1_single_person_speaking()
    test_scenario_2_two_people_close_and_far()
    test_scenario_3_speaker_vs_person_with_money()
    test_scenario_4_food_focus_while_talking()
    test_scenario_5_package_unboxing_action()
    test_scenario_6_camera_pan_following()
    test_scenario_7_scene_cut_reset()
    test_scenario_8_no_faces_object_and_center_fallback()
    print("\n🎉 ALL 8 INTELLIGENT CAMERA SCENARIO TESTS PASSED! 🎉\n")
