import Header from "../components/Header";
import { BookOpen, Sparkles, Gamepad2, Volume2, Wand2 } from "lucide-react";

export default function StoryStudio() {
  return (
    <div className="flex-1 flex flex-col min-h-screen bg-neutral-950 overflow-y-auto">
      <Header
        title="Story Studio"
        subtitle="AI narrative generator combined with procedural gameplay reels."
      />

      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-12 max-w-4xl w-full mx-auto flex flex-col items-center justify-center text-center">
        <div className="relative mb-6">
          <div className="w-18 h-18 rounded-3xl bg-neutral-900 border border-neutral-750 flex items-center justify-center text-amber-400 shadow-2xl">
            <BookOpen className="w-9 h-9" />
          </div>
          <span className="absolute -top-1.5 -right-2 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-mono font-semibold tracking-wide uppercase">
            Coming Soon
          </span>
        </div>

        <h2 className="text-xl sm:text-2xl font-bold text-neutral-100 tracking-tight mb-3">
          Story Studio is in development
        </h2>

        <p className="text-xs sm:text-sm text-neutral-400 max-w-md mb-8 leading-relaxed">
          Generate random suspense and drama stories with synthetic AI voice narration, automatically spliced over dynamic 9:16 gameplay footage (Minecraft, Subway Surfers, GTA).
        </p>

        {/* Feature Teasers */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-xl text-left">
          <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 space-y-1.5">
            <div className="w-7 h-7 rounded-lg bg-neutral-850 flex items-center justify-center text-amber-400 mb-2">
              <Wand2 className="w-4 h-4" />
            </div>
            <h4 className="text-xs font-semibold text-neutral-200">AI Story Scripting</h4>
            <p className="text-[11px] text-neutral-500">
              Generate suspenseful Reddit stories, horror, and curiosity hooks.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 space-y-1.5">
            <div className="w-7 h-7 rounded-lg bg-neutral-850 flex items-center justify-center text-teal-400 mb-2">
              <Volume2 className="w-4 h-4" />
            </div>
            <h4 className="text-xs font-semibold text-neutral-200">Neural TTS Voice</h4>
            <p className="text-[11px] text-neutral-500">
              Realistic, emotive voice synthesis with timed audio ducking.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 space-y-1.5">
            <div className="w-7 h-7 rounded-lg bg-neutral-850 flex items-center justify-center text-blue-400 mb-2">
              <Gamepad2 className="w-4 h-4" />
            </div>
            <h4 className="text-xs font-semibold text-neutral-200">Gameplay Stitching</h4>
            <p className="text-[11px] text-neutral-500">
              Automatic background gameplay alignment and captions.
            </p>
          </div>
        </div>

        <div className="mt-8 text-[11px] font-mono text-neutral-500">
          Planned for Clipreator v2.1 • Separate module
        </div>
      </main>
    </div>
  );
}
