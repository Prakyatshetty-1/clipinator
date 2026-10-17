import { Terminal, Disc, Activity, Bell } from "lucide-react";

export default function Header({ title, subtitle, onOpenTerminalModal }) {
  return (
    <header className="h-16 px-6 lg:px-8 bg-neutral-950/70 border-b border-neutral-850/80 backdrop-blur-md flex items-center justify-between sticky top-0 z-10 shrink-0">
      <div className="flex flex-col">
        <h1 className="text-base font-semibold text-neutral-100 tracking-tight flex items-center gap-2">
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs text-neutral-400 font-normal">
            {subtitle}
          </p>
        )}
      </div>

      {/* Right Desktop Utilities */}
      <div className="flex items-center gap-3">
        {/* CLI Connected Tag */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-md bg-neutral-900 border border-neutral-800 text-[11px] font-mono text-neutral-300">
          <Terminal className="w-3.5 h-3.5 text-amber-400" />
          <span>clipreator --daemon</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </div>

        {/* Local Ollama / Whisper VRAM status */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-md bg-neutral-900 border border-neutral-800 text-[11px] text-neutral-400">
          <Activity className="w-3.5 h-3.5 text-blue-400" />
          <span>VRAM: <span className="text-neutral-200 font-mono">4.2 / 12 GB</span></span>
        </div>
      </div>
    </header>
  );
}
