"""Active speaker and audio-visual speech analyzer for Clipreator.

Combines:
1. Audio stream energy / voice activity
2. Visual lip/mouth motion dynamics across consecutive video frames
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


@dataclass
class SpeakerCue:
    face_idx: int
    mouth_motion: float   # 0.0 to 1.0
    audio_energy: float   # 0.0 to 1.0
    speaker_score: float  # Combined active speaker relevance (0.0 to 1.0)


class SpeakerAnalyzer:
    AUDIO_SAMPLE_RATE = 8000
    WINDOW_SECS = 0.35

    def __init__(self, audio_path: str | None = None) -> None:
        self.audio_samples: np.ndarray | None = None
        self.sample_rate = self.AUDIO_SAMPLE_RATE
        self._prev_mouths: dict[int, np.ndarray] = {}
        if audio_path:
            self._load_audio(audio_path)

    def _load_audio(self, video_or_audio_path: str) -> None:
        """Loads audio track as 8kHz mono PCM to compute short-term RMS energy."""
        try:
            cmd = [
                "ffmpeg", "-v", "error", "-y",
                "-i", video_or_audio_path,
                "-vn", "-ar", str(self.AUDIO_SAMPLE_RATE), "-ac", "1",
                "-f", "s16le", "-"
            ]
            proc = subprocess.run(cmd, capture_output=True, check=False)
            if proc.returncode == 0 and len(proc.stdout) > 0:
                raw = np.frombuffer(proc.stdout, dtype=np.int16)
                self.audio_samples = raw.astype(np.float32) / 32768.0
        except Exception:
            self.audio_samples = None

    def get_audio_energy(self, timestamp: float) -> float:
        """Returns normalized audio RMS energy [0.0, 1.0] at the given timestamp."""
        if self.audio_samples is None or len(self.audio_samples) == 0:
            return 0.5  # Neutral default if no audio track is available

        center = int(timestamp * self.sample_rate)
        half_win = int(self.WINDOW_SECS * self.sample_rate / 2)
        start = max(0, center - half_win)
        end = min(len(self.audio_samples), center + half_win)

        if start >= end:
            return 0.0

        segment = self.audio_samples[start:end]
        rms = float(np.sqrt(np.mean(segment ** 2)))
        # Normalize: typical voice speech RMS in 16-bit audio ranges 0.02 to 0.25
        normalized = min(1.0, max(0.0, (rms - 0.01) / 0.15))
        return normalized

    def analyze_mouth(self, frame_bgr: np.ndarray, face_idx: int, bbox: Sequence[float]) -> float:
        """Estimates visual mouth movement dynamics in the lower third of the face."""
        x1, y1, x2, y2 = (int(v) for v in bbox[:4])
        fh = max(1, y2 - y1)
        fw = max(1, x2 - x1)

        # Mouth region: lower 35% of face, horizontally centered middle 60%
        my1 = int(y1 + 0.65 * fh)
        my2 = min(frame_bgr.shape[0], y2)
        mx1 = int(x1 + 0.20 * fw)
        mx2 = min(frame_bgr.shape[1], int(x1 + 0.80 * fw))

        if my2 <= my1 or mx2 <= mx1:
            return 0.0

        crop = frame_bgr[my1:my2, mx1:mx2]
        small = cv2.resize(crop, (48, 32), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        prev = self._prev_mouths.get(face_idx)
        self._prev_mouths[face_idx] = gray

        if prev is None:
            return 0.0

        # Frame difference in mouth region
        diff = cv2.absdiff(gray, prev)
        motion_intensity = float(np.mean(diff)) / 255.0

        # Normalize: active mouth motion ranges 0.015 to 0.12
        motion_score = min(1.0, max(0.0, (motion_intensity - 0.01) / 0.08))
        return motion_score

    def score_speaker(
        self,
        frame_bgr: np.ndarray,
        faces: Sequence[Sequence[float]],
        timestamp: float,
    ) -> list[SpeakerCue]:
        """Calculates speaker cues for each detected face."""
        audio_energy = self.get_audio_energy(timestamp)
        cues: list[SpeakerCue] = []

        for idx, face_bbox in enumerate(faces):
            mouth_motion = self.analyze_mouth(frame_bgr, idx, face_bbox)
            # High score when both audio energy and mouth movement co-occur
            # (or strong mouth movement alone)
            if audio_energy > 0.2:
                speaker_score = 0.6 * mouth_motion + 0.4 * audio_energy
            else:
                speaker_score = 0.3 * mouth_motion

            cues.append(
                SpeakerCue(
                    face_idx=idx,
                    mouth_motion=mouth_motion,
                    audio_energy=audio_energy,
                    speaker_score=max(0.0, min(1.0, speaker_score)),
                )
            )

        return cues

    def reset(self) -> None:
        self._prev_mouths.clear()
