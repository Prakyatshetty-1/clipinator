import { Loader2, Sparkles, CheckCircle2 } from "lucide-react";
import ProcessingStep from "./ProcessingStep";
import { PIPELINE_STEPS } from "../services/clipGenerator";

export default function ProcessingPipeline({
  currentStepIndex,
  completedSteps,
  isFinished
}) {
  const total = PIPELINE_STEPS.length;
  const progressPercent = Math.min(
    100,
    Math.round(((completedSteps.length + (isFinished ? 0 : 0.5)) / total) * 100)
  );

  return (
    <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-6 lg:p-8 shadow-2xl backdrop-blur-md max-w-3xl mx-auto my-6 animate-in fade-in duration-300">
      {/* Workflow Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-neutral-850">
        <div>
          <div className="flex items-center gap-2 mb-1">
            {!isFinished ? (
              <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            )}
            <h3 className="text-base font-semibold text-neutral-100">
              {isFinished ? "Generation Complete" : "Generating your clips..."}
            </h3>
          </div>
          <p className="text-xs text-neutral-400">
            {isFinished
              ? "All pipeline stages completed successfully."
              : "Running Whisper, Qwen 2.5, FFmpeg, and the reframer on your machine. This can take several minutes."}
          </p>
        </div>
      </div>

      {/* Overall Progress Bar */}
      <div className="my-5">
        <div className="flex items-center justify-between text-xs font-mono text-neutral-400 mb-2">
          <span>Pipeline Progress</span>
          <span className="text-neutral-200 font-semibold">{progressPercent}%</span>
        </div>
        <div className="w-full h-1.5 bg-neutral-950 rounded-full overflow-hidden border border-neutral-800">
          <div
            className="h-full bg-gradient-to-r from-amber-500 via-amber-400 to-emerald-400 transition-all duration-300 ease-out rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* 7 Pipeline Steps */}
      <div className="space-y-2 mt-4">
        {PIPELINE_STEPS.map((step, idx) => {
          let status = "pending";
          if (completedSteps.includes(idx) || isFinished) {
            status = "completed";
          } else if (idx === currentStepIndex) {
            status = "processing";
          }

          return (
            <ProcessingStep
              key={step.id}
              stepNumber={step.stepNumber}
              label={step.label}
              detail={step.detail}
              status={status}
            />
          );
        })}
      </div>

      {/* Final Complete Notice */}
      {isFinished && (
        <div className="mt-6 p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between animate-in fade-in duration-300">
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-emerald-300">
                Generation Complete
              </p>
              <p className="text-[11px] text-emerald-400/80 font-mono">
                Clips generated and reframed for vertical display.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
