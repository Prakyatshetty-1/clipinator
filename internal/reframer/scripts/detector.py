"""Local face/person detectors. No cloud APIs.

Priority:
1. InsightFace buffalo_l (same family as vertical_video_convertor) if installed
2. OpenCV YuNet (tiny ONNX, cached locally)
3. Haar cascade fallback
4. HOG pedestrians when no faces are found
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from face_tracker import DetectedFace

YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_NAME = "face_detection_yunet_2023mar.onnx"


def _even(value: int) -> int:
    return max(2, int(value) // 2 * 2)


@dataclass
class DetectorInfo:
    name: str
    device: str


class SubjectDetector:
    def __init__(self, model_dir: str, use_gpu: bool = True, det_size: int = 640) -> None:
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.det_size = det_size
        self._insight = None
        self._yunet = None
        self._yunet_size: tuple[int, int] | None = None
        self._haar = None
        self._hog = None
        self.info = DetectorInfo(name="none", device="cpu")
        self._init_backend()

    def _init_backend(self) -> None:
        if self._try_insightface():
            return
        if self._try_yunet():
            return
        cascade = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade):
            self._haar = cv2.CascadeClassifier(cascade)
            self.info = DetectorInfo(name="haar", device="cpu")

    def _try_insightface(self) -> bool:
        try:
            from insightface.app import FaceAnalysis
        except Exception:
            return False

        providers = ["CPUExecutionProvider"]
        device = "cpu"
        if self.use_gpu:
            try:
                import onnxruntime as ort

                if "CUDAExecutionProvider" in ort.get_available_providers():
                    providers.insert(0, "CUDAExecutionProvider")
                    device = "cuda"
            except Exception:
                pass

        try:
            app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection"], providers=providers)
            app.prepare(ctx_id=0 if device == "cuda" else -1, det_size=(self.det_size, self.det_size))
            self._insight = app
            self.info = DetectorInfo(name="insightface", device=device)
            return True
        except Exception as exc:
            print(f"[reframe] InsightFace unavailable ({exc}); trying YuNet", flush=True)
            return False

    def _try_yunet(self) -> bool:
        model_path = self.model_dir / YUNET_NAME
        if not model_path.exists() or model_path.stat().st_size < 50000:
            if model_path.exists():
                try:
                    model_path.unlink()
                except OSError:
                    pass
            print(f"[reframe] Downloading YuNet face model to {model_path} ...", flush=True)
            downloaded = False
            try:
                import subprocess
                res = subprocess.run(
                    ["curl", "-L", "--connect-timeout", "15", "-o", str(model_path), YUNET_URL],
                    capture_output=True,
                )
                if res.returncode == 0 and model_path.exists() and model_path.stat().st_size >= 50000:
                    downloaded = True
            except Exception:
                pass

            if not downloaded:
                try:
                    req = urllib.request.Request(YUNET_URL, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp, open(model_path, "wb") as f:
                        f.write(resp.read())
                    if model_path.stat().st_size >= 50000:
                        downloaded = True
                except Exception as exc:
                    print(f"[reframe] YuNet download failed: {exc}", flush=True)
                    if model_path.exists():
                        try:
                            model_path.unlink()
                        except OSError:
                            pass
                    return False

        try:
            detector = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), 0.6, 0.3, 5000)
            self._yunet = detector
            self.info = DetectorInfo(name="yunet", device="cpu")
            return True
        except Exception as exc:
            print(f"[reframe] YuNet init failed: {exc}", flush=True)
            return False

    def _hog_detector(self):
        if self._hog is None:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        return self._hog

    def detect(self, frame: np.ndarray) -> list[DetectedFace]:
        faces: list[DetectedFace] = []
        if self._insight is not None:
            try:
                raw = self._insight.get(frame)
                for face in raw:
                    bbox = [float(v) for v in face.bbox[:4]]
                    faces.append(DetectedFace(bbox=bbox, det_score=float(getattr(face, "det_score", 1.0))))
            except Exception:
                faces = []
        elif self._yunet is not None:
            h, w = frame.shape[:2]
            size = (_even(w), _even(h))
            if self._yunet_size != size:
                self._yunet.setInputSize(size)
                self._yunet_size = size
            try:
                _retval, detections = self._yunet.detect(frame)
            except cv2.error:
                detections = None
            if detections is not None:
                for det in detections:
                    x, y, bw, bh = det[:4]
                    score = float(det[-1]) if len(det) > 4 else 1.0
                    faces.append(
                        DetectedFace(
                            bbox=[float(x), float(y), float(x + bw), float(y + bh)],
                            det_score=score,
                        )
                    )
        elif self._haar is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found = self._haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
            for x, y, bw, bh in found:
                faces.append(DetectedFace(bbox=[float(x), float(y), float(x + bw), float(y + bh)], det_score=1.0))

        if faces:
            return faces

        try:
            rects, weights = self._hog_detector().detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        except Exception:
            return []
        people: list[DetectedFace] = []
        for (x, y, bw, bh), weight in zip(rects, weights):
            people.append(
                DetectedFace(
                    bbox=[float(x), float(y), float(x + bw), float(y + bh)],
                    det_score=float(weight[0] if hasattr(weight, "__len__") else weight),
                )
            )
        return people
