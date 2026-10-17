import { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  X,
  Download,
  Flame,
  Clock,
  Check
} from "lucide-react";

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export default function VideoPreviewModal({ clip, isOpen, onClose, onExport }) {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    const video = videoRef.current;
    if (!isOpen || !video) return;
    setProgress(0);
    setCurrentTime(0);
    setIsPlaying(true);
    video.currentTime = 0;
    video.play().catch(() => setIsPlaying(false));
  }, [isOpen, clip?.videoUrl]);

  if (!isOpen || !clip) return null;

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) {
      setIsPlaying((prev) => !prev);
      return;
    }
    if (video.paused) {
      video.play();
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleExport = () => {
    setIsExporting(true);
    onExport(clip);
    setTimeout(() => setIsExporting(false), 500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="absolute inset-0" onClick={onClose} />

      <div className="relative z-10 w-full max-w-4xl max-h-[95vh] bg-neutral-900 border border-neutral-750 rounded-2xl shadow-2xl flex flex-col lg:flex-row overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="relative bg-neutral-950 flex items-center justify-center p-4 lg:p-6 border-b lg:border-b-0 lg:border-r border-neutral-800">
          <div className="relative aspect-[9/16] w-64 sm:w-72 max-h-[68vh] rounded-xl overflow-hidden shadow-2xl border border-white/10 bg-black">
            {clip.videoUrl ? (
              <video
                ref={videoRef}
                src={clip.videoUrl}
                className="absolute inset-0 w-full h-full object-contain bg-black"
                muted={isMuted}
                playsInline
                onTimeUpdate={(e) => {
                  const el = e.currentTarget;
                  setCurrentTime(el.currentTime);
                  if (el.duration) {
                    setProgress((el.currentTime / el.duration) * 100);
                  }
                }}
                onEnded={() => setIsPlaying(false)}
                onClick={togglePlay}
              />
            ) : (
              <div className={`absolute inset-0 bg-gradient-to-t ${clip.accentColor || "from-amber-600/30 to-neutral-950"}`} />
            )}

            <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
              <span className="px-2 py-0.5 rounded bg-black/70 backdrop-blur-md text-[10px] font-mono text-neutral-200 border border-white/10">
                CLIP {clip.clipNumber} • 1080x1920
              </span>
              {clip.score ? (
                <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-black/70 backdrop-blur-md text-[10px] font-mono text-emerald-400 border border-emerald-500/30">
                  <Flame className="w-3 h-3 text-emerald-400" />
                  <span>{clip.score}</span>
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={togglePlay}
              className="absolute inset-0 bottom-14 z-10 flex items-center justify-center bg-transparent"
            >
              {!isPlaying && (
                <div className="w-14 h-14 rounded-full bg-black/60 backdrop-blur-md border border-white/20 flex items-center justify-center text-amber-400 shadow-xl">
                  <Play className="w-6 h-6 ml-1 fill-current" />
                </div>
              )}
            </button>

            <div className="absolute bottom-3 left-3 right-3 z-20 space-y-1.5 bg-black/70 p-2 rounded-lg backdrop-blur-md border border-white/5">
              <div
                onClick={(e) => {
                  const video = videoRef.current;
                  if (!video?.duration) return;
                  const rect = e.currentTarget.getBoundingClientRect();
                  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                  video.currentTime = ratio * video.duration;
                }}
                className="w-full h-1.5 bg-white/20 rounded-full cursor-pointer relative overflow-hidden"
              >
                <div
                  className="h-full bg-amber-400 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-neutral-300">
                <span>{formatTime(currentTime)}</span>
                <span>{clip.durationFormatted}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col justify-between p-6 bg-neutral-900">
          <div>
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-neutral-800">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-semibold">
                  Vertical Clip Inspector
                </span>
                <h3 className="text-lg font-bold text-neutral-100 mt-1 leading-snug">
                  "{clip.title}"
                </h3>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition-colors"
                title="Close modal (Esc)"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex items-center gap-3 py-4 border-b border-neutral-800/80">
              <button
                type="button"
                onClick={togglePlay}
                className="p-2 rounded-lg bg-neutral-800 hover:bg-neutral-750 text-neutral-200 transition-colors flex items-center gap-2 text-xs font-medium"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                <span>{isPlaying ? "Pause" : "Play"}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  const video = videoRef.current;
                  const next = !isMuted;
                  setIsMuted(next);
                  if (video) video.muted = next;
                }}
                className="p-2 rounded-lg bg-neutral-800 hover:bg-neutral-750 text-neutral-200 transition-colors flex items-center gap-2 text-xs font-medium"
              >
                {isMuted ? (
                  <VolumeX className="w-4 h-4 text-rose-400" />
                ) : (
                  <Volume2 className="w-4 h-4 text-neutral-200" />
                )}
                <span>{isMuted ? "Muted" : "Volume"}</span>
              </button>

              <button
                type="button"
                onClick={() => videoRef.current?.requestFullscreen?.()}
                className="p-2 rounded-lg bg-neutral-800 hover:bg-neutral-750 text-neutral-200 transition-colors flex items-center gap-2 text-xs font-medium ml-auto"
                title="Fullscreen preview"
              >
                <Maximize2 className="w-4 h-4" />
                <span className="hidden sm:inline">Fullscreen</span>
              </button>
            </div>

            <div className="space-y-3.5 py-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800">
                  <span className="text-[10px] text-neutral-500 font-mono block">AI Viral Score</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Flame className="w-4 h-4 text-emerald-400" />
                    <span className="text-base font-bold text-neutral-100">{clip.score || "—"}/100</span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800">
                  <span className="text-[10px] text-neutral-500 font-mono block">Duration</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Clock className="w-4 h-4 text-amber-400" />
                    <span className="text-base font-bold text-neutral-100">{clip.durationFormatted}</span>
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-neutral-950/70 border border-neutral-800 space-y-2">
                <div className="flex items-center justify-between text-[11px] text-neutral-400">
                  <span>Reframing Strategy</span>
                  <span className="font-mono text-neutral-200 font-medium">{clip.reframingMode}</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-neutral-400">
                  <span>Captions Preset</span>
                  <span className="font-mono text-neutral-200">Word-by-Word Highlight (9:16)</span>
                </div>
              </div>

              <div>
                <span className="text-[11px] text-neutral-400 block mb-1.5">Extracted Transcript Quote:</span>
                <p className="p-3 rounded-xl bg-neutral-950/50 border border-neutral-800/80 text-neutral-300 italic text-[11px] leading-relaxed">
                  "{clip.transcriptSnippet || clip.hook || clip.title}"
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-neutral-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl text-neutral-400 hover:text-neutral-200 text-xs font-medium hover:bg-neutral-800 transition-colors"
            >
              Close
            </button>

            <button
              type="button"
              onClick={handleExport}
              disabled={isExporting}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold shadow-lg transition-all cursor-pointer ${
                isExporting
                  ? "bg-emerald-600 text-white"
                  : "bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-amber-950/40"
              }`}
            >
              {isExporting ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Downloading</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>Download Clip</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
