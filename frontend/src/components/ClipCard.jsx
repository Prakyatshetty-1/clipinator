import { useState } from "react";
import { Play, Download, Sparkles, Clock, Volume2, Check, Share2, Flame } from "lucide-react";

export default function ClipCard({ clip, onPreview, onExport }) {
  const [isExporting, setIsExporting] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const handleExportClick = (e) => {
    e.stopPropagation();
    setIsExporting(true);
    setTimeout(() => {
      setIsExporting(false);
      onExport(clip);
    }, 600);
  };

  // Determine score color accent
  const getScoreColor = (score) => {
    if (score >= 93) return "text-emerald-400 bg-emerald-950/70 border-emerald-500/40";
    if (score >= 88) return "text-amber-400 bg-amber-950/70 border-amber-500/40";
    return "text-blue-400 bg-blue-950/70 border-blue-500/40";
  };

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="group relative flex flex-col bg-neutral-900/60 hover:bg-neutral-900 border border-neutral-800 hover:border-neutral-700/80 rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-neutral-950/80 hover:-translate-y-1"
    >
      {/* 9:16 Vertical Video Preview Container */}
      <div
        onClick={() => onPreview(clip)}
        className="relative aspect-[9/16] w-full bg-neutral-950 overflow-hidden cursor-pointer flex flex-col justify-between p-3.5 select-none"
      >
        {clip.videoUrl ? (
          <video
            src={clip.videoUrl}
            className="absolute inset-0 w-full h-full object-cover"
            muted
            playsInline
            preload="metadata"
          />
        ) : (
          <div
            className={`absolute inset-0 bg-gradient-to-b ${clip.accentColor || "from-neutral-800 to-neutral-950"} opacity-70 group-hover:scale-105 transition-transform duration-500 ease-out`}
          />
        )}

        {/* Dynamic Scanlines & Vignette */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_40%,rgba(0,0,0,0.85)_100%)] pointer-events-none" />

        {/* Audio Waveform Simulation Bar at top */}
        <div className="relative z-10 flex items-center justify-between">
          <span className="px-2 py-0.5 rounded-md bg-neutral-950/80 backdrop-blur-md text-neutral-200 font-mono text-[10px] font-bold tracking-wider border border-white/10 shadow-sm">
            CLIP {clip.clipNumber}
          </span>

          <div
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md border backdrop-blur-md text-[10px] font-mono font-semibold ${getScoreColor(
              clip.score
            )}`}
          >
            <Flame className="w-3 h-3" />
            <span>Score {clip.score}</span>
          </div>
        </div>

        {/* Center Hover Play Button */}
        <div className="relative z-10 flex flex-col items-center justify-center my-auto transition-transform duration-200 group-hover:scale-110">
          <div className="w-13 h-13 rounded-full bg-neutral-950/70 backdrop-blur-md border border-white/20 flex items-center justify-center text-amber-400 group-hover:bg-amber-500 group-hover:text-neutral-950 group-hover:border-amber-400 shadow-xl transition-all duration-200">
            <Play className="w-6 h-6 ml-1 fill-current" />
          </div>

          <span className="text-[10px] text-neutral-400 group-hover:text-neutral-200 font-medium tracking-wide mt-2 bg-neutral-950/60 px-2 py-0.5 rounded-full backdrop-blur-sm">
            Click to Preview
          </span>
        </div>

        {/* Bottom Subtitle / Kinetic Caption Simulation */}
        <div className="relative z-10 space-y-2">
          {clip.captionsEnabled && (
            <div className="px-2.5 py-1.5 rounded-lg bg-neutral-950/85 backdrop-blur-md border border-neutral-800/80 shadow-md">
              <span className="text-[11px] font-bold text-amber-300 leading-tight block drop-shadow font-sans text-center">
                "{(clip.transcriptSnippet || clip.title || "").slice(0, 58)}{(clip.transcriptSnippet || "").length > 58 ? "..." : ""}"
              </span>
            </div>
          )}

          {/* Time & Reframing Badges */}
          <div className="flex items-center justify-between text-[10px] font-mono text-neutral-300">
            <div className="flex items-center gap-1 bg-black/60 px-2 py-0.5 rounded backdrop-blur-sm">
              <Clock className="w-3 h-3 text-neutral-400" />
              <span>{clip.durationFormatted}</span>
            </div>

            <span className="bg-black/60 px-1.5 py-0.5 rounded text-[9px] text-neutral-400 truncate max-w-[110px]">
              9:16 Smart Crop
            </span>
          </div>
        </div>
      </div>

      {/* Card Body & Metadata */}
      <div className="p-4 flex flex-col flex-1 justify-between gap-3">
        <div>
          <h4
            onClick={() => onPreview(clip)}
            className="text-sm font-semibold text-neutral-100 hover:text-amber-400 transition-colors line-clamp-1 cursor-pointer"
            title={clip.title}
          >
            "{clip.title}"
          </h4>

          {clip.subtitle && (
            <p className="text-xs text-neutral-400 mt-1 line-clamp-2">
              {clip.subtitle}
            </p>
          )}

          {/* Tag Pills */}
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {clip.tags?.slice(0, 2).map((tag, idx) => (
              <span
                key={idx}
                className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 border border-neutral-750"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Card Action Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-800/70">
          <button
            type="button"
            onClick={() => onPreview(clip)}
            className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium transition-colors border border-neutral-700/60 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
            <span>Preview</span>
          </button>

          <button
            type="button"
            onClick={handleExportClick}
            disabled={isExporting}
            className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-medium transition-all cursor-pointer ${
              isExporting
                ? "bg-emerald-600 text-white"
                : "bg-amber-500/10 hover:bg-amber-500 text-amber-400 hover:text-neutral-950 border border-amber-500/30 hover:border-amber-500"
            }`}
          >
            {isExporting ? (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Exported</span>
              </>
            ) : (
              <>
                <Download className="w-3.5 h-3.5" />
                <span>Export</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
