#!/usr/bin/env python3
"""Smart 9:16 reframer for Clipreator.

Features:
- Tracks faces, people, and objects with persistent IDs across frames.
- Spoken context & object grounding using faster-whisper transcripts.
- Active speaker detection combining Whisper VAD timestamps + mouth dynamics.
- Weighted context-aware candidate selection with dwell-time and hysteresis.
- Scene-cut detection and tracking reset.
- Fast sampling with intermediate track velocity projection.
- Smooth camera easing with dead-zone and boundary clamping.
- Debug mode with visual overlay and decision logs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from camera_planner import IntelligentCameraPlanner
from detector import DetectedEntity, SubjectDetector
from scene_detector import SceneCutDetector
from smoothing import CropSmoother, TargetSmoother


def _even(value: float) -> int:
    return max(2, round(value / 2) * 2)


def _probe(path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate,nb_frames:format=duration",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("no video stream")
    num, _, den = str(video.get("avg_frame_rate", "0/1")).partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    if fps <= 0:
        fps = 30.0
    try:
        frames = int(video.get("nb_frames") or 0)
    except (TypeError, ValueError):
        frames = 0
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    duration = float(data.get("format", {}).get("duration") or 0)
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "frames": frames,
        "has_audio": has_audio,
        "duration": duration,
    }


def _clamp_origin(cx: float, cy: float, crop_w: int, crop_h: int, frame_w: int, frame_h: int) -> tuple[int, int]:
    left = cx - crop_w / 2.0
    top = cy - crop_h / 2.0
    left = min(max(left, 0.0), float(max(0, frame_w - crop_w)))
    top = min(max(top, 0.0), float(max(0, frame_h - crop_h)))
    return int(round(left)), int(round(top))


def _write_sendcmd(path: Path, commands: list[tuple[float, int, int]]) -> None:
    lines: list[str] = []
    last_x = last_y = None
    for t, x, y in commands:
        if x != last_x:
            lines.append(f"{t:.4f} crop x {x};")
            last_x = x
        if y != last_y:
            lines.append(f"{t:.4f} crop y {y};")
            last_y = y
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _video_encoders(use_gpu: bool = True) -> list[list[str]]:
    encoders = []
    if use_gpu:
        encoders.append(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"])
    encoders.append(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
    return encoders


def _run_ffmpeg(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _first_xy(commands: list[tuple[float, int, int]]) -> tuple[int, int]:
    if not commands:
        return 0, 0
    return commands[0][1], commands[0][2]


def _encode_sendcmd(
    input_path: str,
    output_path: str,
    cmd_file: Path,
    crop_w: int,
    crop_h: int,
    out_w: int,
    out_h: int,
    has_audio: bool,
    origin: tuple[int, int],
    use_gpu: bool = True,
) -> bool:
    vf = (
        f"sendcmd=f={cmd_file.as_posix()},"
        f"crop={crop_w}:{crop_h}:{origin[0]}:{origin[1]},"
        f"scale={out_w}:{out_h}"
    )
    for enc in _video_encoders(use_gpu):
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf, "-map", "0:v:0", *enc]
        if has_audio:
            cmd += ["-map", "0:a:0", "-c:a", "copy"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart", "-shortest", output_path]
        if _run_ffmpeg(cmd).returncode == 0:
            return True
        if has_audio:
            cmd = [
                "ffmpeg", "-y", "-i", input_path, "-vf", vf, "-map", "0:v:0", *enc,
                "-map", "0:a:0", "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", "-shortest", output_path,
            ]
            if _run_ffmpeg(cmd).returncode == 0:
                return True
    return False


def _render_cv2(
    input_path: str,
    temp_video: Path,
    commands: list[tuple[float, int, int]],
    crop_w: int,
    crop_h: int,
    fps: float,
) -> None:
    cap = cv2.VideoCapture(input_path)
    writer = cv2.VideoWriter(str(temp_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (crop_w, crop_h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("could not open OpenCV video writer")
    try:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            _, x, y = commands[min(idx, len(commands) - 1)]
            cropped = frame[y : y + crop_h, x : x + crop_w]
            if cropped.shape[1] != crop_w or cropped.shape[0] != crop_h:
                cropped = cv2.resize(cropped, (crop_w, crop_h), interpolation=cv2.INTER_AREA)
            writer.write(cropped)
            idx += 1
    finally:
        cap.release()
        writer.release()


def _mux_scaled(
    temp_video: Path,
    source: str,
    output_path: str,
    out_w: int,
    out_h: int,
    has_audio: bool,
    use_gpu: bool = True,
) -> None:
    vf = f"scale={out_w}:{out_h}"
    for enc in _video_encoders(use_gpu):
        if has_audio:
            copy_cmd = [
                "ffmpeg", "-y", "-i", str(temp_video), "-i", source,
                "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, *enc,
                "-c:a", "copy", "-movflags", "+faststart", "-shortest", output_path,
            ]
            if _run_ffmpeg(copy_cmd).returncode == 0:
                return
            aac_cmd = [
                "ffmpeg", "-y", "-i", str(temp_video), "-i", source,
                "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, *enc,
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", output_path,
            ]
            if _run_ffmpeg(aac_cmd).returncode == 0:
                return
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(temp_video), "-vf", vf, *enc,
                "-an", "-movflags", "+faststart", output_path,
            ]
            if _run_ffmpeg(cmd).returncode == 0:
                return
    raise RuntimeError("ffmpeg mux failed")


def reframe(args: argparse.Namespace) -> None:
    info = _probe(args.input)
    frame_w, frame_h, fps = info["width"], info["height"], info["fps"]
    use_gpu = not args.cpu

    # 1. Exact 9:16 aspect ratio geometry
    target_aspect = args.width / float(args.height)  # 1080 / 1920 = 0.5625
    source_aspect = frame_w / float(frame_h)

    if source_aspect >= target_aspect:
        # Landscape or wide video: crop height spans full source height
        crop_h = _even(frame_h)
        crop_w = _even(crop_h * target_aspect)
    else:
        # Narrow / vertical video: crop width spans full source width
        crop_w = _even(frame_w)
        crop_h = _even(crop_w / target_aspect)

    if crop_w >= frame_w and crop_h >= frame_h:
        # Already vertical / exact target aspect: scale directly
        vf = f"scale={args.width}:{args.height}:force_original_aspect_ratio=increase,crop={args.width}:{args.height}"
        for enc in _video_encoders(use_gpu):
            cmd = [
                "ffmpeg", "-y", "-i", args.input, "-vf", vf, *enc,
                "-c:a", "copy", "-movflags", "+faststart", args.output,
            ]
            if _run_ffmpeg(cmd).returncode == 0:
                print("[reframe] source already vertical; scaled to target 9:16", flush=True)
                return
        raise RuntimeError("ffmpeg scale failed")

    # 2. Initialize Detectors, Trackers & Planner
    detector = SubjectDetector(model_dir=args.model_dir, use_gpu=use_gpu, det_size=args.det_size)
    print(f"[reframe] detector={detector.info.name} device={detector.info.device} yolo={detector.info.yolo_loaded}", flush=True)

    planner = IntelligentCameraPlanner(
        frame_width=frame_w,
        frame_height=frame_h,
        crop_width=crop_w,
        crop_height=crop_h,
        hold_seconds=args.hold_seconds,
        context_path=args.context,
    )
    if info.get("has_audio"):
        planner.set_audio_path(args.input)

    smoother = TargetSmoother(frame_w, frame_h, crop_w, fps, refocus_band_fraction=args.refocus_band)
    crop_smoother = CropSmoother()
    scene = SceneCutDetector(threshold=args.scene_threshold)
    headroom_shift = (0.5 - args.headroom) * crop_h

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError(f"could not open {args.input}")

    commands: list[tuple[float, int, int]] = []
    detections_count = 0
    processed = 0
    sample_interval = max(1, args.sample_interval)

    # Optional debug video writer
    debug_writer = None
    if args.debug:
        debug_out_path = str(Path(args.output).with_suffix(".debug.mp4"))
        debug_writer = cv2.VideoWriter(debug_out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame_w, frame_h))
        print(f"[reframe-debug] writing visual diagnostics to {debug_out_path}", flush=True)

    cached_entities: list[DetectedEntity] = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            now = processed / fps

            is_scene_cut = scene.update(frame)
            if is_scene_cut:
                planner.reset()
                smoother.reset(frame_w / 2.0, frame_h / 2.0)
                crop_smoother.reset()

            # Keyframe sampling: run full neural detector on interval or scene cut
            if is_scene_cut or (processed % sample_interval == 0) or not cached_entities:
                cached_entities = detector.detect_entities(frame)
                if cached_entities:
                    detections_count += 1

            target = planner.update(frame, cached_entities, now)

            if is_scene_cut:
                smoother.reset(target[0], target[1] + headroom_shift)
                crop_smoother.reset()

            sx, sy = smoother.update(target[0], target[1] + headroom_shift)
            left, top = _clamp_origin(sx, sy, crop_w, crop_h, frame_w, frame_h)
            left, top = crop_smoother.update(left, top)
            commands.append((now, left, top))

            # Debug visual overlay
            if debug_writer is not None:
                dbg_frame = frame.copy()
                # 1. Draw entities
                for t in planner.tracker.tracks.values():
                    bx1, by1, bx2, by2 = [int(v) for v in t.bbox]
                    color = (0, 255, 0) if t.is_active_speaker else (255, 200, 0) if t.category == "object" else (255, 120, 0)
                    cv2.rectangle(dbg_frame, (bx1, by1), (bx2, by2), color, 2)
                    label_str = f"#{t.track_id} {t.label}"
                    if t.speaker_score > 0.2:
                        label_str += f" spk:{t.speaker_score:.2f}"
                    cv2.putText(dbg_frame, label_str, (bx1, max(15, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

                # 2. Draw 9:16 crop rectangle
                cv2.rectangle(dbg_frame, (left, top), (left + crop_w, top + crop_h), (0, 0, 255), 3)
                # 3. Draw diagnostic text
                target_cand = planner._last_selected_candidate
                tgt_info = f"t={now:.2f}s | Target: {target_cand.id if target_cand else 'center'} ({target_cand.reason if target_cand else ''})"
                cv2.putText(dbg_frame, tgt_info, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                debug_writer.write(dbg_frame)

            processed += 1
            if processed % 60 == 0:
                print(f"[reframe] analyzed {processed} frames", flush=True)
    finally:
        cap.release()
        if debug_writer is not None:
            debug_writer.release()

    if processed == 0:
        raise RuntimeError("no frames decoded")

    hit_rate = detections_count / max(1, processed // sample_interval)
    print(f"[reframe] detected subjects on {detections_count} sampled frames ({hit_rate:.0%})", flush=True)

    # 3. Output encoding
    out_parent = Path(args.output).resolve().parent
    out_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clipreator_reframe_", dir=str(out_parent)) as tmp:
        tmp_path = Path(tmp)
        cmd_file = tmp_path / "crop.cmd"
        _write_sendcmd(cmd_file, commands)
        origin = _first_xy(commands)
        if _encode_sendcmd(
            args.input, args.output, cmd_file, crop_w, crop_h, args.width, args.height, info["has_audio"], origin, use_gpu=use_gpu
        ):
            print("[reframe] encoded with ffmpeg sendcmd crop", flush=True)
            return
        print("[reframe] sendcmd encode failed; falling back to frame crop", flush=True)
        temp_video = tmp_path / "video_only.mp4"
        _render_cv2(args.input, temp_video, commands, crop_w, crop_h, fps)
        _mux_scaled(temp_video, args.input, args.output, args.width, args.height, info["has_audio"], use_gpu=use_gpu)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart 9:16 context-aware vertical reframer")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--headroom", type=float, default=0.42)
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--scene-threshold", type=float, default=28.0)
    parser.add_argument("--refocus-band", type=float, default=0.03)
    parser.add_argument("--det-size", type=int, default=640)
    parser.add_argument("--sample-interval", type=int, default=4, help="Keyframe detection interval in frames (default 4)")
    parser.add_argument("--context", default=None, help="Path to clip transcript and highlight context JSON")
    parser.add_argument("--debug", action="store_true", help="Generate annotated diagnostic video with bounding boxes and crop window")
    parser.add_argument("--model-dir", default=os.path.expanduser("~/.clipreator/models"))
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    try:
        reframe(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
