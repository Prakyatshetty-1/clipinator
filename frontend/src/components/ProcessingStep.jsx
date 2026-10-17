import { Check, Loader2, Circle } from "lucide-react";

export default function ProcessingStep({
  stepNumber,
  label,
  detail,
  status // 'pending' | 'processing' | 'completed'
}) {
  return (
    <div
      className={`flex items-start gap-4 p-3.5 rounded-xl transition-all duration-200 border ${
        status === "processing"
          ? "bg-neutral-850/80 border-amber-500/40 shadow-lg shadow-amber-950/20"
          : status === "completed"
          ? "bg-neutral-900/40 border-neutral-800/60"
          : "bg-neutral-950/20 border-transparent opacity-50"
      }`}
    >
      {/* State Icon Indicator */}
      <div className="pt-0.5 shrink-0">
        {status === "completed" && (
          <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center text-emerald-400">
            <Check className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
        )}

        {status === "processing" && (
          <div className="w-6 h-6 rounded-full bg-amber-500/20 border border-amber-500/60 flex items-center justify-center text-amber-400">
            <Loader2 className="w-3.5 h-3.5 animate-spin stroke-[2.5]" />
          </div>
        )}

        {status === "pending" && (
          <div className="w-6 h-6 rounded-full bg-neutral-800/40 border border-neutral-700/60 flex items-center justify-center text-neutral-500">
            <Circle className="w-2.5 h-2.5 fill-current" />
          </div>
        )}
      </div>

      {/* Step Label & Detail */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-neutral-500 font-semibold">
              {stepNumber}
            </span>
            <span
              className={`text-xs font-medium ${
                status === "processing"
                  ? "text-neutral-100 font-semibold"
                  : status === "completed"
                  ? "text-neutral-300"
                  : "text-neutral-500"
              }`}
            >
              {label}
            </span>
          </div>

          {/* Status Badge Text */}
          <div className="shrink-0 font-mono text-[11px]">
            {status === "completed" && (
              <span className="text-emerald-400 font-medium">✓ Complete</span>
            )}
            {status === "processing" && (
              <span className="text-amber-400 animate-pulse font-medium">
                ◉ Processing...
              </span>
            )}
            {status === "pending" && (
              <span className="text-neutral-600">○ Waiting</span>
            )}
          </div>
        </div>

        {detail && (
          <p
            className={`text-[11px] mt-0.5 truncate ${
              status === "processing" ? "text-neutral-400" : "text-neutral-600"
            }`}
          >
            {detail}
          </p>
        )}
      </div>
    </div>
  );
}
