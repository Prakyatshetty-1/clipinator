import { Film, Sparkles, ArrowUp } from "lucide-react";

export default function EmptyState({ onSampleClick, cachedClips, onViewCached }) {
  return (
    <div className="py-12 px-6 text-center border border-dashed border-neutral-800/80 rounded-2xl bg-neutral-950/30 flex flex-col items-center justify-center max-w-lg mx-auto my-6">
      <div className="w-12 h-12 rounded-2xl bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400 mb-3 shadow-inner">
        <Film className="w-6 h-6 text-neutral-400" />
      </div>

      <h3 className="text-sm font-medium text-neutral-200 mb-1">
        Your generated clips will appear here.
      </h3>

      <p className="text-xs text-neutral-500 max-w-xs mb-4">
        Paste a video URL or upload raw footage above to get started.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-2.5">
        {cachedClips && cachedClips.clips?.length > 0 && (
          <button
            type="button"
            onClick={onViewCached}
            className="inline-flex items-center gap-1.5 text-xs text-emerald-300 hover:text-emerald-200 font-medium px-3.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 transition-all cursor-pointer shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>View {cachedClips.clips.length} Recent Generated Clips</span>
          </button>
        )}

        {onSampleClick && (
          <button
            type="button"
            onClick={onSampleClick}
            className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 font-medium px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Load demo sample URL</span>
          </button>
        )}
      </div>
    </div>
  );
}
