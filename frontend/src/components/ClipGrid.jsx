import { CheckCircle2, RotateCcw, Download, Sparkles, SlidersHorizontal } from "lucide-react";
import ClipCard from "./ClipCard";

export default function ClipGrid({
  generationResult,
  clips,
  onReset,
  onPreviewClip,
  onExportClip,
  onExportAll
}) {
  const sourceName =
    generationResult?.source || "video.mp4";
  const processingTime =
    generationResult?.processingTime || "00:42";
  const clipCount = clips?.length || 3;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      {/* Generation Complete Summary Card */}
      <div className="bg-neutral-900/90 border border-neutral-750 rounded-2xl p-5 lg:p-6 shadow-xl backdrop-blur-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
            <CheckCircle2 className="w-5 h-5 stroke-[2.5]" />
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-neutral-100">
                Generation Complete
              </span>
              <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800/80">
                {clipCount} clips ready
              </span>
            </div>

            <p className="text-xs text-neutral-400">
              <span className="text-neutral-500">Source:</span>{" "}
              <span className="font-mono text-neutral-300 truncate max-w-sm inline-block align-bottom">
                {sourceName}
              </span>
            </p>

            <div className="flex items-center gap-4 text-[11px] text-neutral-400 font-mono pt-0.5">
              <span>
                Processing time: <strong className="text-neutral-200">{processingTime}</strong>
              </span>
              <span>•</span>
              <span>
                Aspect ratio: <strong className="text-neutral-200">9:16 Vertical</strong>
              </span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 self-end sm:self-center">
          {onExportAll && (
            <button
              type="button"
              onClick={onExportAll}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium transition-colors border border-neutral-700/80 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-amber-400" />
              <span>Download All</span>
            </button>
          )}

          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-semibold shadow-lg shadow-amber-950/40 transition-all cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Generate More</span>
          </button>
        </div>
      </div>

      {/* Generated Clips Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2">
        <div>
          <h2 className="text-lg font-semibold text-neutral-100 tracking-tight">
            Generated Clips
          </h2>
          <p className="text-xs text-neutral-400">
            Your AI-selected moments are ready.
          </p>
        </div>

        <div className="text-xs font-mono text-neutral-400">
          Showing <span className="text-neutral-200 font-semibold">{clips.length}</span> extracted vertical clips
        </div>
      </div>

      {/* Responsive Grid of 9:16 Video Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {clips.map((clip) => (
          <ClipCard
            key={clip.id}
            clip={clip}
            onPreview={onPreviewClip}
            onExport={onExportClip}
          />
        ))}
      </div>
    </div>
  );
}
