#!/usr/bin/env python3
"""Faster-Whisper Medium transcription engine for Clipreator.

Features:
- Uses faster-whisper WhisperModel("medium") directly via Python API
- CUDA GPU acceleration (RTX 3050 6GB) with configurable compute type (float16 / int8_float16)
- Preserves segment and word-level timestamps (word_timestamps=True)
- Automatic language detection (supports English, Hindi, Hinglish, multilingual)
- Reusable model caching (no re-downloading)
- Output compatible with Clipreator Transcript data structures
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import site
from pathlib import Path


def _setup_cuda_library_paths():
    """Auto-detect and enable NVIDIA CUDA shared libraries for ctranslate2.

    ctranslate2 is typically built against CUDA 12 (libcublas.so.12, libcudart.so.12),
    but many venvs ship CUDA 13 via nvidia-* namespace packages. We:
      1. Add nvidia/cu*/lib, nvidia/cudnn/lib, torch/lib to LD_LIBRARY_PATH
         (MUST happen BEFORE the first ctranslate2 import because dlopen reads
          LD_LIBRARY_PATH once at process startup for transitive deps.)
      2. Create missing forward-compat symlinks (libXXX.so.12 -> libXXX.so.13)
         when only CUDA 13 sonames are present. This is safe because NVIDIA
         guarantees minor-version forward compatibility for libcublas/libcudart.
    """
    extra_ld_dirs = []
    cu_dirs = []

    try:
        sitepkgs = site.getsitepackages()
    except Exception:
        sitepkgs = []

    for sp in sitepkgs:
        if not os.path.isdir(sp):
            continue
        # nvidia namespace packages (cu11/cu12/cu13, cudnn, nccl, cusparselt)
        nv_root = os.path.join(sp, "nvidia")
        if os.path.isdir(nv_root):
            for sub in sorted(os.listdir(nv_root)):
                libd = os.path.join(nv_root, sub, "lib")
                if os.path.isdir(libd):
                    extra_ld_dirs.append(libd)
                    if sub.lower().startswith("cu"):
                        cu_dirs.append(libd)
        # torch bundled CUDA libs
        torchlib = os.path.join(sp, "torch", "lib")
        if os.path.isdir(torchlib):
            extra_ld_dirs.append(torchlib)

    # Deduplicate preserving order
    seen = set()
    ordered = []
    for d in extra_ld_dirs:
        rp = os.path.realpath(d)
        if rp in seen:
            continue
        seen.add(rp)
        ordered.append(d)

    # Apply LD_LIBRARY_PATH to env (inherited by subprocesses if any)
    # and to the current process via ctypes if possible.
    cur_ld = os.environ.get("LD_LIBRARY_PATH", "")
    if ordered:
        prefix = os.pathsep.join(ordered)
        new_ld = prefix + (os.pathsep + cur_ld if cur_ld else "")
        os.environ["LD_LIBRARY_PATH"] = new_ld
        try:
            import ctypes
            for libdir in ordered:
                if not os.path.isdir(libdir):
                    continue
                # Explicitly preload cublasLt, cublas, and cudart with RTLD_GLOBAL
                for libname in [
                    "libcublasLt.so.12", "libcublasLt.so.13",
                    "libcublas.so.12", "libcublas.so.13",
                    "libcudart.so.12", "libcudart.so.13",
                    "libcudnn.so.9", "libcudnn.so.8"
                ]:
                    so_path = os.path.join(libdir, libname)
                    if os.path.exists(so_path):
                        try:
                            ctypes.CDLL(so_path, ctypes.RTLD_GLOBAL)
                        except Exception:
                            pass
        except Exception:
            pass

    # Create forward-compat symlinks: CUDA 13 sonames -> CUDA 12 sonames
    # ctranslate2 is built against CUDA 12 ABI and needs these specific names.
    symlinks = {
        "libcublas.so.12":    "libcublas.so.13",
        "libcublasLt.so.12":  "libcublasLt.so.13",
        "libcudart.so.12":    "libcudart.so.13",
        "libnvJitLink.so.12": "libnvJitLink.so.13",
        "libnvrtc.so.12":     "libnvrtc.so.13",
    }
    for libdir in cu_dirs:
        for new_name, existing_name in symlinks.items():
            src = os.path.join(libdir, existing_name)
            dst = os.path.join(libdir, new_name)
            if not os.path.exists(src):
                continue
            if os.path.islink(dst) or os.path.exists(dst):
                try:
                    cur_target = os.readlink(dst)
                    if cur_target == existing_name:
                        continue
                except OSError:
                    pass
                try:
                    os.remove(dst)
                except OSError:
                    continue
            try:
                os.symlink(existing_name, dst)
            except OSError:
                pass  # non-writable venv is OK


_setup_cuda_library_paths()


def _patch_pyav_metadata_errors():
    """Workaround: PyAV 19+ removed the metadata_errors argument from av.open(),
    but faster-whisper <= 1.2.1 still passes it. Wrap av.open() to strip the arg.
    """
    try:
        import av as _av
    except ImportError:
        return

    _orig_av_open = _av.open

    def _wrapped_av_open(file, mode="r", **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(file, mode=mode, **kwargs)

    _av.open = _wrapped_av_open


_patch_pyav_metadata_errors()


def log_config(engine: str, model: str, device: str, compute_type: str) -> None:
    print(f"Transcription engine: {engine}", flush=True)
    print(f"Model: {model}", flush=True)
    print(f"Device: {device.upper()}", flush=True)
    print(f"Compute type: {compute_type}", flush=True)


def _cuda_actually_works() -> bool:
    """Best-effort check that ctranslate2 can really use CUDA."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _resolve_device_and_compute(requested_device: str, requested_compute: str):
    """Return a (device, compute_type, from_fallback_note) tuple with fallbacks.

    We never hard-exit on a bad CUDA setup. Instead we walk a cascade of
    known-good combos and pick the first that is actually usable on this box.
    """
    cuda_ok = (requested_device.lower() == "cuda") and _cuda_actually_works()

    combos = []
    if cuda_ok:
        # Prefer user's exact request first
        combos.append(("cuda", requested_compute, None))
        # Still offer CUDA fallbacks for missing libs / OOM / bad combos
        cuda_fallbacks = [
            ("cuda", "float16"),
            ("cuda", "int8_float16"),
            ("cuda", "int8"),
            ("cuda", "float32"),
        ]
        for d, c in cuda_fallbacks:
            if (d, c) != combos[0][:2]:
                combos.append((d, c, f"CUDA fallback: {requested_compute} → {c}"))
    # Always append CPU fallbacks (universally supported)
    cpu_fallbacks = [
        ("cpu", "int8"),
        ("cpu", "int8_float32"),
        ("cpu", "float32"),
        ("cpu", "default"),
    ]
    for d, c in cpu_fallbacks:
        combos.append((d, c, f"CPU fallback: {requested_device}/{requested_compute} not available"))

    # Remove duplicates preserving order
    seen = set()
    deduped = []
    for d, c, note in combos:
        key = (d, c)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((d, c, note))
    return deduped


def load_model(
    model_name: str,
    device: str,
    compute_type: str,
    download_root: str | None = None,
):
    from faster_whisper import WhisperModel

    combos = _resolve_device_and_compute(device, compute_type)
    last_exc = None

    for idx, (dev, ct, note) in enumerate(combos):
        try:
            if idx == 0:
                header_note = ""
            else:
                header_note = f"  ({note})"
            print(
                f"🧠 Trying WhisperModel('{model_name}', device={dev}, compute_type={ct}){header_note}",
                flush=True,
            )
            model = WhisperModel(
                model_name,
                device=dev,
                compute_type=ct,
                download_root=download_root,
            )
            # Always record actual successful combo (even idx=0, direct success)
            _last_device[0] = dev
            _last_compute[0] = ct
            if idx > 0:
                print(
                    f"✅ Loaded on {dev.upper()}/{ct} (auto-selected after prior failures)",
                    flush=True,
                )
            else:
                print(
                    f"✅ Loaded on {dev.upper()}/{ct}",
                    flush=True,
                )
            return model
        except Exception as exc:
            last_exc = exc
            is_last = idx == len(combos) - 1
            msg = str(exc)
            if is_last:
                print(f"❌ Final candidate combo failed ({dev}/{ct}): {msg}", file=sys.stderr)
            else:
                print(
                    f"⚠️  Combo {dev}/{ct} did not work: {msg.strip().splitlines()[-1]}",
                    flush=True,
                )
            continue

    # We only land here if *every* combo failed (extremely rare)
    print(
        f"\n❌ Fatal: could not load faster-whisper model with any device/compute combo.",
        file=sys.stderr,
    )
    print(f"   Last error: {last_exc}\n", file=sys.stderr)
    sys.exit(3)


_last_device = [""]
_last_compute = [""]


def _override_report_device_compute(device: str, compute_type: str):
    """If auto-fallback picked something else, report that instead."""
    if _last_device[0] and _last_compute[0]:
        return _last_device[0], _last_compute[0]
    return device, compute_type


def check_cuda_availability(requested_device: str) -> None:
    """Soft, non-fatal check. We don't exit anymore - the cascade handles it."""
    if requested_device.lower() != "cuda":
        return
    if _cuda_actually_works():
        return
    print(
        "ℹ️  CUDA requested but not fully available (missing driver/cuda/libcublas). "
        "Will auto-fallback to CPU.",
        flush=True,
    )


def transcribe_audio(
    audio_path: str,
    output_dir: str,
    model_name: str = "medium",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str | None = None,
    download_root: str | None = None,
) -> dict:
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    os.makedirs(output_dir, exist_ok=True)
    check_cuda_availability(device)

    # Reset last-used tracking in case this function is called multiple times
    _last_device[0] = ""
    _last_compute[0] = ""

    model = load_model(
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        download_root=download_root,
    )

    # Report actual used device/compute (may differ from requested due to fallback)
    real_device, real_compute = _override_report_device_compute(device, compute_type)
    log_config("faster-whisper", model_name, real_device, real_compute)
    print(f"🎙️  Transcribing '{Path(audio_path).name}' with faster-whisper...", flush=True)

    try:
        segments_gen, info = model.transcribe(
            audio_path,
            language=language if language and language.strip() != "" else None,
            word_timestamps=True,
            vad_filter=True,
        )

        detected_lang = info.language if info and info.language else "unknown"
        lang_prob = info.language_probability if info and info.language_probability else 0.0
        print(
            f"🌐 Detected language: {detected_lang} (confidence: {lang_prob:.1%})",
            flush=True,
        )

        transcript_segments = []
        full_text_parts = []

        for seg in segments_gen:
            clean_seg_text = seg.text.strip()
            full_text_parts.append(clean_seg_text)

            words_list = []
            if getattr(seg, "words", None):
                for w in seg.words:
                    words_list.append(
                        {
                            "word": w.word,
                            "start": round(float(w.start), 3),
                            "end": round(float(w.end), 3),
                        }
                    )

            transcript_segments.append(
                {
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": clean_seg_text,
                    "words": words_list,
                }
            )

    except Exception as exc:
        err_msg = str(exc).lower()
        if "out of memory" in err_msg:
            print(
                "\n❌ Error: CUDA Out Of Memory (OOM) during transcription.",
                file=sys.stderr,
            )
            print(
                "   👉 Fix: Switch compute type to int8_float16:",
                file=sys.stderr,
            )
            print(
                "      export WHISPER_COMPUTE_TYPE=int8_float16\n",
                file=sys.stderr,
            )
            sys.exit(2)
        raise

    full_transcript_text = " ".join(full_text_parts)
    payload = {
        "text": full_transcript_text,
        "segments": transcript_segments,
        "language": detected_lang,
    }

    # Write output audio.json in standard Clipreator format
    json_path = os.path.join(output_dir, "audio.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Also write plain text audio.txt for convenience
    txt_path = os.path.join(output_dir, "audio.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_transcript_text + "\n")

    print(
        f"✅ Transcription complete: {len(transcript_segments)} segments saved to {json_path}",
        flush=True,
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="faster-whisper Medium transcription for Clipreator")
    parser.add_argument("--audio", required=True, help="Input audio or video file path")
    parser.add_argument("--output-dir", required=True, help="Output directory for audio.json")
    parser.add_argument("--model", default="medium", help="Whisper model name (default: medium)")
    parser.add_argument(
        "--device",
        default=os.getenv("WHISPER_DEVICE", "cuda"),
        help="Device to use: cuda or cpu (default: cuda)",
    )
    parser.add_argument(
        "--compute-type",
        default=os.getenv("WHISPER_COMPUTE_TYPE", "float16"),
        help="CTranslate2 compute type: float16, int8_float16, int8, float32 (default: float16)",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("WHISPER_LANGUAGE", None),
        help="Optional language code (default: auto-detect)",
    )
    parser.add_argument(
        "--download-root",
        default=os.getenv("CLIPREATOR_MODEL_DIR", None),
        help="Model cache root directory",
    )

    args = parser.parse_args()

    # Support dev override: setting WHISPER_MODEL_OVERRIDE lets us use smaller models for testing
    # without removing the production default of "medium" when args.model is the default.
    override = os.getenv("WHISPER_MODEL_OVERRIDE")
    if override:
        model_name = override
    elif os.getenv("WHISPER_MODEL"):
        model_name = os.getenv("WHISPER_MODEL")
    else:
        model_name = args.model
        # Enforce Medium model per requirement when no explicit env override is provided
        if model_name not in {"tiny", "base", "small", "medium", "large-v3"}:
            model_name = "medium"

    try:
        transcribe_audio(
            audio_path=args.audio,
            output_dir=args.output_dir,
            model_name=model_name,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            download_root=args.download_root,
        )
    except Exception as exc:
        print(f"Error during transcription: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
