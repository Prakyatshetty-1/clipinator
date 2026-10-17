"""Context and spoken-object grounding for Clipreator 9:16 reframing.

Extracts referenced objects from faster-whisper transcript segments and
Qwen highlight metadata, then grounds candidate objects detected in the video.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass
class SpokenTarget:
    keywords: list[str]
    category_labels: list[str]
    start: float
    end: float
    phrase: str
    weight: float = 1.0


# Mapping of spoken trigger vocabulary to YOLO and detection labels
OBJECT_VOCABULARY = [
    {
        "keywords": ["phone", "iphone", "android", "smartphone", "mobile", "cellphone", "screen"],
        "labels": ["cell phone", "prop"],
        "weight": 1.25,
    },
    {
        "keywords": ["laptop", "macbook", "computer", "pc", "keyboard", "monitor", "display", "gpu", "graphics card", "motherboard"],
        "labels": ["laptop", "tv", "keyboard", "prop"],
        "weight": 1.25,
    },
    {
        "keywords": ["money", "cash", "rupees", "dollar", "dollars", "bills", "prize", "jackpot", "notes"],
        "labels": ["prop", "money_prop"],
        "weight": 1.30,
    },
    {
        "keywords": ["food", "burger", "pizza", "sandwich", "apple", "banana", "snack", "dish", "bowl", "plate", "cake", "eat", "eating"],
        "labels": ["food", "bowl", "sandwich", "apple", "banana", "pizza", "hot dog"],
        "weight": 1.20,
    },
    {
        "keywords": ["bottle", "drink", "water", "can", "cup", "coffee", "beer", "wine", "glass", "mug"],
        "labels": ["bottle", "cup", "wine glass"],
        "weight": 1.15,
    },
    {
        "keywords": ["car", "vehicle", "automobile", "truck", "bike", "motorcycle", "drive", "driving"],
        "labels": ["car", "motorcycle", "bicycle", "truck", "bus"],
        "weight": 1.20,
    },
    {
        "keywords": ["box", "package", "unboxing", "unbox", "gift", "present", "case", "parcel"],
        "labels": ["prop", "suitcase", "backpack"],
        "weight": 1.25,
    },
    {
        "keywords": ["book", "notebook", "paper", "document", "contract"],
        "labels": ["book", "prop"],
        "weight": 1.10,
    },
    {
        "keywords": ["ball", "bat", "racket", "club", "game", "toy"],
        "labels": ["sports ball", "baseball bat", "tennis racket", "prop"],
        "weight": 1.15,
    },
]

DEMONSTRATION_CUES = [
    "look at this", "look at that", "check this out", "check out",
    "watch this", "this is", "here is", "holding", "take a look",
    "see this", "right here", "unboxing", "presenting"
]


class ContextGrounder:
    """Interprets transcript and clip highlights to score visual object relevance."""

    def __init__(self, context_path: str | Path | None = None) -> None:
        self.targets: list[SpokenTarget] = []
        self.clip_title = ""
        self.clip_hook = ""
        self.clip_why = ""
        if context_path:
            self.load_context(context_path)

    def load_context(self, context_path: str | Path) -> None:
        path = Path(context_path)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.clip_title = str(data.get("title", ""))
            self.clip_hook = str(data.get("hook", ""))
            self.clip_why = str(data.get("why", ""))
            words = data.get("words", [])
            self._extract_targets(words)
        except Exception:
            self.targets = []

    def _extract_targets(self, words: list[dict]) -> None:
        """Finds target objects referenced in words and associates time windows."""
        if not words:
            # Fallback: check hook / title for general object focus
            full_context = f"{self.clip_title} {self.clip_hook} {self.clip_why}".lower()
            for rule in OBJECT_VOCABULARY:
                for kw in rule["keywords"]:
                    if re.search(r"\b" + re.escape(kw) + r"\b", full_context):
                        self.targets.append(
                            SpokenTarget(
                                keywords=rule["keywords"],
                                category_labels=rule["labels"],
                                start=0.0,
                                end=9999.0,
                                phrase=kw,
                                weight=rule["weight"] * 0.85,
                            )
                        )
                        break
            return

        # Scan word list
        n = len(words)
        for i, w in enumerate(words):
            word_text = str(w.get("text", "")).strip().lower()
            w_start = float(w.get("start", 0.0))
            w_end = float(w.get("end", w_start + 0.3))

            # Check matching vocabulary
            for rule in OBJECT_VOCABULARY:
                matched_kw = None
                for kw in rule["keywords"]:
                    if kw in word_text:
                        matched_kw = kw
                        break

                if matched_kw:
                    # Look ahead / behind for demonstration cues (e.g., "look at this phone")
                    window_words = [
                        words[j].get("text", "").lower()
                        for j in range(max(0, i - 4), min(n, i + 5))
                    ]
                    surrounding_phrase = " ".join(window_words)
                    is_demo = any(cue in surrounding_phrase for cue in DEMONSTRATION_CUES)
                    weight = rule["weight"] * (1.30 if is_demo else 1.0)

                    # Expand active window: 0.5s before mention, 2.5s after mention
                    self.targets.append(
                        SpokenTarget(
                            keywords=rule["keywords"],
                            category_labels=rule["labels"],
                            start=max(0.0, w_start - 0.5),
                            end=w_end + 3.0,
                            phrase=surrounding_phrase,
                            weight=weight,
                        )
                    )

    def evaluate_object_relevance(
        self,
        object_bbox: Sequence[float],
        object_label: str,
        timestamp: float,
        person_bboxes: Sequence[Sequence[float]] | None = None,
    ) -> float:
        """Calculates contextual relevance score [0.0, 1.0] for a detected object."""
        if not self.targets:
            # Baseline score for known interactive props even without explicit text
            if object_label in ("food", "prop", "money_prop", "cell phone", "laptop"):
                return 0.40
            return 0.20

        max_relevance = 0.0
        for target in self.targets:
            if target.start <= timestamp <= target.end:
                # Check label match
                matches = (object_label in target.category_labels) or (
                    any(kw in object_label for kw in target.keywords)
                )
                if matches:
                    rel = 0.70 * target.weight

                    # Person-Object Proximity: If object is held by or adjacent to a person
                    if person_bboxes:
                        ox1, oy1, ox2, oy2 = object_bbox[:4]
                        for p_box in person_bboxes:
                            px1, py1, px2, py2 = p_box[:4]
                            # Distance or overlap
                            dx = max(0.0, max(px1 - ox2, ox1 - px2))
                            dy = max(0.0, max(py1 - oy2, oy1 - py2))
                            if dx < (px2 - px1) * 0.35 and dy < (py2 - py1) * 0.45:
                                rel *= 1.25  # Interacting / held object bonus
                                break

                    max_relevance = max(max_relevance, min(1.0, rel))

        return max_relevance
