from face_tracker import DetectedFace, FaceTracker
from smoothing import TargetSmoother


def test_two_people_fit():
    tracker = FaceTracker(1920, 1080, crop_width=608, hold_seconds=2.0)
    left = DetectedFace(bbox=[200, 200, 320, 360], det_score=0.9)
    right = DetectedFace(bbox=[420, 210, 540, 370], det_score=0.9)
    cx, cy = tracker.update([left, right], 0.0)
    assert 300 < cx < 460, cx
    assert 250 < cy < 330, cy


def test_two_people_too_far_picks_one():
    tracker = FaceTracker(1920, 1080, crop_width=608, hold_seconds=2.0)
    left = DetectedFace(bbox=[40, 200, 200, 420], det_score=0.99)
    right = DetectedFace(bbox=[1600, 200, 1800, 420], det_score=0.5)
    cx, _cy = tracker.update([left, right], 0.0)
    assert cx < 400, cx


def test_sticky_does_not_ping_pong():
    tracker = FaceTracker(1920, 1080, crop_width=608, hold_seconds=2.0)
    a = DetectedFace(bbox=[200, 200, 360, 400], det_score=0.8)
    b = DetectedFace(bbox=[1400, 200, 1560, 400], det_score=0.81)
    c1, _ = tracker.update([a, b], 0.0)
    a2 = DetectedFace(bbox=[200, 200, 360, 400], det_score=0.79)
    b2 = DetectedFace(bbox=[1400, 200, 1560, 400], det_score=0.85)
    c2, _ = tracker.update([a2, b2], 0.04)
    assert abs(c1 - c2) < 80, (c1, c2)


def test_smoother_speed_cap():
    s = TargetSmoother(1920, 1080, 608, fps=30.0, refocus_band_fraction=0.03)
    s.reset(960, 540)
    x, y = s.update(200, 540)
    assert abs(x - 960) < 608 / 30 + 5
    assert abs(y - 540) < 2


def test_hold_on_dropout():
    tracker = FaceTracker(1920, 1080, crop_width=608, hold_seconds=2.0)
    face = DetectedFace(bbox=[200, 200, 360, 400], det_score=0.9)
    c1, _ = tracker.update([face], 0.0)
    c2, _ = tracker.update([], 0.5)
    assert c1 == c2
    missing = tracker.update([], 3.0)
    assert missing is None


if __name__ == "__main__":
    test_two_people_fit()
    test_two_people_too_far_picks_one()
    test_sticky_does_not_ping_pong()
    test_smoother_speed_cap()
    test_hold_on_dropout()
    print("tracker tests passed")
