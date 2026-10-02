#!/usr/bin/env python3
"""Smart 9:16 reframer for Clipreator.

Tracks faces/people, eases the crop like a camera, snaps on scene cuts,
then encodes once with ffmpeg so the source audio can be stream-copied.
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

from detector import SubjectDetector
from face_tracker import FaceTracker
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
    left = min(max(left, 0.0), float(frame_w - crop_w))
    top = min(max(top, 0.0), float(frame_h - crop_h))
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


def _mux_scaled(temp_video: Path, source: str, output_path: str, out_w: int, out_h: int, has_audio: bool, use_gpu: bool = True) -> None:
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
    crop_h = _even(frame_h)
    crop_w = _even(crop_h * 9 / 16)
    use_gpu = not args.cpu
    if crop_w > frame_w:
        # Already vertical / too narrow: scale only.
        vf = f"scale={args.width}:{args.height}:force_original_aspect_ratio=increase,crop={args.width}:{args.height}"
        for enc in _video_encoders(use_gpu):
            cmd = [
                "ffmpeg", "-y", "-i", args.input, "-vf", vf, *enc,
                "-c:a", "copy", "-movflags", "+faststart", args.output,
            ]
            if _run_ffmpeg(cmd).returncode == 0:
                print("[reframe] source already vertical; scaled to target 9:16", flush=True)
                return
            cmd = [
                "ffmpeg", "-y", "-i", args.input, "-vf", vf, *enc,
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", args.output,
            ]
            if _run_ffmpeg(cmd).returncode == 0:
                print("[reframe] source already vertical; scaled to target 9:16", flush=True)
                return
        raise RuntimeError("ffmpeg scale failed")

    detector = SubjectDetector(model_dir=args.model_dir, use_gpu=not args.cpu, det_size=args.det_size)
    print(f"[reframe] detector={detector.info.name} device={detector.info.device}", flush=True)

    tracker = FaceTracker(frame_w, frame_h, crop_w, hold_seconds=args.hold_seconds)
    smoother = TargetSmoother(frame_w, frame_h, crop_w, fps, refocus_band_fraction=args.refocus_band)
    crop_smoother = CropSmoother()
    scene = SceneCutDetector(threshold=args.scene_threshold)
    headroom_shift = (0.5 - args.headroom) * crop_h
    frame_center = (frame_w / 2.0, frame_h / 2.0)

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError(f"could not open {args.input}")

    commands: list[tuple[float, int, int]] = []
    detections = 0
    processed = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            now = processed / fps
            faces = detector.detect(frame)
            if faces:
                detections += 1
            target = tracker.update(faces, now)
            if scene.update(frame):
                tracker.reset()
                target = tracker.update(faces, now) or frame_center
                smoother.reset(target[0], target[1] + headroom_shift)
                crop_smoother.reset()
            elif target is None:
                target = frame_center

            sx, sy = smoother.update(target[0], target[1] + headroom_shift)
            left, top = _clamp_origin(sx, sy, crop_w, crop_h, frame_w, frame_h)
            left, top = crop_smoother.update(left, top)
            commands.append((now, left, top))
            processed += 1
            if processed % 60 == 0:
                print(f"[reframe] analyzed {processed} frames", flush=True)
    finally:
        cap.release()

    if processed == 0:
        raise RuntimeError("no frames decoded")

    hit_rate = detections / processed
    print(f"[reframe] faces/people on {detections}/{processed} frames ({hit_rate:.0%})", flush=True)
    if hit_rate < 0.02:
        print("[reframe] almost no subjects detected; using center crop path", flush=True)
        commands = [(t, (frame_w - crop_w) // 2, 0) for t, _, _ in commands]

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
    parser = argparse.ArgumentParser(description="Smart 9:16 reframe a landscape clip")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--headroom", type=float, default=0.42)
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--scene-threshold", type=float, default=28.0)
    parser.add_argument("--refocus-band", type=float, default=0.03)
    parser.add_argument("--det-size", type=int, default=640)
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
