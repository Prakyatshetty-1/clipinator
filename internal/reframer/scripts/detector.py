"""Local multi-modal detectors for faces, persons, and objects. No cloud APIs.

Priority:
1. InsightFace buffalo_l (faces) + YOLOv8n (persons, food, props, objects) on GPU
2. OpenCV YuNet (faces)
3. Haar cascade fallback (faces)
4. HOG pedestrians & salient foreground contours (objects/props fallback)
"""

from __future__ import annotations

import ctypes
import glob
import os
import shutil
import site
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


def _setup_cuda_library_paths():
    """Auto-detect and preload NVIDIA CUDA shared libraries for GPU runtime."""
    try:
        sitepkgs = site.getsitepackages()
    except Exception:
        sitepkgs = []

    for sp in sitepkgs:
        nv_root = os.path.join(sp, "nvidia")
        if os.path.isdir(nv_root):
            for libname in [
                "libcudart.so.12", "libcudart.so.13",
                "libcublasLt.so.12", "libcublasLt.so.13",
                "libcublas.so.12", "libcublas.so.13",
                "libcurand.so.10",
            ]:
                matches = glob.glob(os.path.join(nv_root, "**", libname), recursive=True)
                for m in matches:
                    try:
                        ctypes.CDLL(m, ctypes.RTLD_GLOBAL)
                    except Exception:
                        pass


_setup_cuda_library_paths()

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
    yolo_loaded: bool = False


@dataclass
class DetectedEntity:
    bbox: list[float]  # [x1, y1, x2, y2]
    category: str      # 'face', 'person', 'object'
    label: str         # e.g. 'face', 'person', 'food', 'cell phone', 'laptop', 'prop'
    score: float       # Confidence score (0.0 to 1.0)


FOOD_CLASSES = {
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "bowl"
}

PROP_CLASSES = {
    "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "backpack", "umbrella", "handbag", "tie", "suitcase",
    "sports ball", "baseball bat", "baseball glove", "skateboard", "tennis racket",
    "cell phone", "laptop", "mouse", "remote", "keyboard", "book", "clock",
    "vase", "scissors", "teddy bear"
}

VEHICLE_CLASSES = {"car", "motorcycle", "bicycle", "bus", "train", "truck", "boat"}


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
        self._yolo = None
        self.info = DetectorInfo(name="none", device="cpu", yolo_loaded=False)
        self._init_backend()
        self._init_yolo()

    def _init_backend(self) -> None:
        if self._try_insightface():
            return
        if self._try_yunet():
            return
        cascade = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade):
            self._haar = cv2.CascadeClassifier(cascade)
            self.info = DetectorInfo(name="haar", device="cpu", yolo_loaded=False)

    def _init_yolo(self) -> None:
        try:
            from ultralytics import YOLO
            import torch

            target_weights = self.model_dir / "yolov8n.pt"
            local_weights = Path("yolov8n.pt")
            if not target_weights.exists() and local_weights.exists():
                try:
                    shutil.copy(local_weights, target_weights)
                except Exception:
                    pass

            weights_path = str(target_weights if target_weights.exists() else "yolov8n.pt")
            self._yolo = YOLO(weights_path)
            self.info.yolo_loaded = True
        except Exception:
            self._yolo = None
            self.info.yolo_loaded = False

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
            self.info = DetectorInfo(name="insightface", device=device, yolo_loaded=self.info.yolo_loaded)
            return True
        except Exception as exc:
            return False

    def _try_yunet(self) -> bool:
        model_path = self.model_dir / YUNET_NAME
        if not model_path.exists() or model_path.stat().st_size < 50000:
            if model_path.exists():
                try:
                    model_path.unlink()
                except OSError:
                    pass
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
                except Exception:
                    if model_path.exists():
                        try:
                            model_path.unlink()
                        except OSError:
                            pass
                    return False

        try:
            detector = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), 0.6, 0.3, 5000)
            self._yunet = detector
            self.info = DetectorInfo(name="yunet", device="cpu", yolo_loaded=self.info.yolo_loaded)
            return True
        except Exception:
            return False

    def _hog_detector(self):
        if self._hog is None:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        return self._hog

    def detect_faces(self, frame: np.ndarray) -> list[DetectedFace]:
        """Detects faces using InsightFace -> YuNet -> Haar cascade."""
        if frame is None or frame.size == 0:
            return []

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

        return faces

    def detect(self, frame: np.ndarray) -> list[DetectedFace]:
        """Backwards-compatible detect: returns faces or HOG pedestrian fallback."""
        faces = self.detect_faces(frame)
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

    def detect_entities(self, frame: np.ndarray) -> list[DetectedEntity]:
        """Detects all visual entities in the frame: faces, persons, and objects."""
        if frame is None or frame.size == 0:
            return []

        entities: list[DetectedEntity] = []

        # 1. Faces
        faces = self.detect_faces(frame)
        for f in faces:
            entities.append(
                DetectedEntity(
                    bbox=[float(v) for v in f.bbox[:4]],
                    category="face",
                    label="face",
                    score=float(f.det_score),
                )
            )

        # 2. Objects and Persons via YOLOv8
        if self._yolo is not None:
            try:
                import torch
                device = "cuda" if (self.use_gpu and torch.cuda.is_available()) else "cpu"
                results = self._yolo.predict(frame, device=device, verbose=False, conf=0.25)
                for res in results:
                    boxes = res.boxes
                    if boxes is None:
                        continue
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = res.names[cls_id]
                        conf = float(box.conf[0].item())
                        xyxy = [float(v) for v in box.xyxy[0].tolist()]

                        if cls_name == "person":
                            entities.append(
                                DetectedEntity(
                                    bbox=xyxy,
                                    category="person",
                                    label="person",
                                    score=conf,
                                )
                            )
                        elif cls_name in FOOD_CLASSES:
                            entities.append(
                                DetectedEntity(
                                    bbox=xyxy,
                                    category="object",
                                    label="food",
                                    score=conf,
                                )
                            )
                        elif cls_name in PROP_CLASSES:
                            entities.append(
                                DetectedEntity(
                                    bbox=xyxy,
                                    category="object",
                                    label=cls_name,
                                    score=conf,
                                )
                            )
                        elif cls_name in VEHICLE_CLASSES:
                            entities.append(
                                DetectedEntity(
                                    bbox=xyxy,
                                    category="object",
                                    label=cls_name,
                                    score=conf,
                                )
                            )
                        else:
                            entities.append(
                                DetectedEntity(
                                    bbox=xyxy,
                                    category="object",
                                    label=cls_name,
                                    score=conf * 0.85,
                                )
                            )
            except Exception:
                pass

        # 3. Fallback to HOG persons only if neither person nor face was detected
        has_person = any(e.category == "person" for e in entities)
        has_face = any(e.category == "face" for e in entities)
        if not has_person and not has_face:
            try:
                h, w = frame.shape[:2]
                scale = 640.0 / max(w, 1)
                small = cv2.resize(frame, (640, int(h * scale)), interpolation=cv2.INTER_AREA)
                rects, weights = self._hog_detector().detectMultiScale(small, winStride=(16, 16), padding=(8, 8), scale=1.1)
                inv_scale = 1.0 / scale
                for (x, y, bw, bh), weight in zip(rects, weights):
                    score = float(weight[0] if hasattr(weight, "__len__") else weight)
                    entities.append(
                        DetectedEntity(
                            bbox=[float(x * inv_scale), float(y * inv_scale), float((x + bw) * inv_scale), float((y + bh) * inv_scale)],
                            category="person",
                            label="person",
                            score=max(0.5, score),
                        )
                    )
            except Exception:
                pass

        # 4. Salient foreground objects / props (money, packages, items held in hands)
        salient_objects = self._detect_salient_objects(frame, entities)
        entities.extend(salient_objects)

        return entities

    def _detect_salient_objects(
        self,
        frame: np.ndarray,
        existing: list[DetectedEntity],
    ) -> list[DetectedEntity]:
        """Finds prominent foreground objects not caught by standard COCO classes."""
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # Contrast edges
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        scale_x = w / 320.0
        scale_y = h / 180.0
        frame_area = w * h

        objects: list[DetectedEntity] = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            rx1, ry1, rx2, ry2 = x * scale_x, y * scale_y, (x + cw) * scale_x, (y + ch) * scale_y
            area = (rx2 - rx1) * (ry2 - ry1)

            # Looking for medium-sized props (between 1.5% and 35% of the frame)
            if area < 0.015 * frame_area or area > 0.35 * frame_area:
                continue

            # Don't duplicate existing detected faces/persons
            overlap = False
            for ex in existing:
                ex1, ey1, ex2, ey2 = ex.bbox
                ix1, iy1 = max(rx1, ex1), max(ry1, ey1)
                ix2, iy2 = min(rx2, ex2), min(ry2, ey2)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    if inter / area > 0.6:
                        overlap = True
                        break
            if not overlap:
                objects.append(
                    DetectedEntity(
                        bbox=[rx1, ry1, rx2, ry2],
                        category="object",
                        label="prop",
                        score=0.65,
                    )
                )

        # Keep top 3 most prominent salient props
        objects.sort(key=lambda o: (o.bbox[2] - o.bbox[0]) * (o.bbox[3] - o.bbox[1]), reverse=True)
        return objects[:3]
