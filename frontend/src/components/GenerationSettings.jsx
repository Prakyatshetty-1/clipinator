import { useState } from "react";
import { SlidersHorizontal, ChevronDown, ChevronUp, Cpu, Mic, Crop, Type, Layers, Sparkles } from "lucide-react";

export default function GenerationSettings({ settings, setSettings, isProcessing }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const updateSetting = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value
    }));
  };

  return (
    <div className="bg-neutral-900/40 border border-neutral-800/80 rounded-2xl overflow-hidden transition-all duration-200">
      {/* Header Toggle */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <SlidersHorizontal className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-semibold text-neutral-200 tracking-wide uppercase">
            Generation Settings
          </span>
          <span className="text-[11px] text-neutral-500 hidden sm:inline">
            (Aspect ratio, AI model, reframing & captions)
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick preview pills when collapsed */}
          {!isExpanded && (
            <div className="hidden md:flex items-center gap-2 text-[11px] font-mono text-neutral-400">
              <span className="px-2 py-0.5 rounded bg-neutral-800 border border-neutral-750 text-neutral-300">
                {settings.aspectRatio || "9:16"}
              </span>
              <span className="px-2 py-0.5 rounded bg-neutral-800 border border-neutral-750 text-neutral-300">
                {settings.clipCount || "Auto"} clips
              </span>
              <span className="px-2 py-0.5 rounded bg-neutral-800 border border-neutral-750 text-neutral-300">
                Captions: {settings.captions ? "On" : "Off"}
              </span>
            </div>
          )}

          <div className="p-1 rounded-md text-neutral-400 hover:text-neutral-200">
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </div>
        </div>
      </button>

      {/* Expandable Settings Grid */}
      {isExpanded && (
        <div className="p-5 border-t border-neutral-800/80 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 bg-neutral-950/40">
          {/* 1. Clip Count */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Clip Count</span>
            </label>
            <select
              value={settings.clipCount || "Auto"}
              onChange={(e) => updateSetting("clipCount", e.target.value)}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="Auto">Auto (AI-detected peaks)</option>
              <option value="1">1 Short Clip</option>
              <option value="3">3 Highlight Clips</option>
              <option value="5">5 Best Moments</option>
              <option value="8">8 Comprehensive Clips</option>
            </select>
          </div>

          {/* 2. Aspect Ratio */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Crop className="w-3.5 h-3.5 text-blue-400" />
              <span>Aspect Ratio</span>
            </label>
            <select
              value={settings.aspectRatio || "9:16"}
              onChange={(e) => updateSetting("aspectRatio", e.target.value)}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="9:16">9:16 (Shorts / TikTok / Reels)</option>
              <option value="1:1">1:1 (Square - Instagram Feed)</option>
              <option value="16:9">16:9 (Landscape - YouTube)</option>
            </select>
          </div>

          {/* 3. Captions */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Type className="w-3.5 h-3.5 text-emerald-400" />
              <span>Captions</span>
            </label>
            <select
              value={settings.captions ? "Enabled" : "Disabled"}
              onChange={(e) => updateSetting("captions", e.target.value === "Enabled")}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="Enabled">Enabled (Kinetic Word Highlight)</option>
              <option value="Disabled">Disabled (No overlay)</option>
            </select>
          </div>

          {/* 4. Smart Reframing */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-violet-400" />
              <span>Smart Reframing</span>
            </label>
            <select
              value={settings.smartReframing ? "Enabled" : "Disabled"}
              onChange={(e) => updateSetting("smartReframing", e.target.value === "Enabled")}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="Enabled">Enabled (Speaker + Camera Intent)</option>
              <option value="Center">Center Static Crop</option>
              <option value="Disabled">Disabled</option>
            </select>
          </div>

          {/* 5. AI Model */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-amber-400" />
              <span>AI Model</span>
            </label>
            <select
              value={settings.aiModel || "Qwen 2.5"}
              onChange={(e) => updateSetting("aiModel", e.target.value)}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="Qwen 2.5">Qwen 2.5 (7B Local Instruct)</option>
              <option value="Qwen 2.5 14B">Qwen 2.5 (14B High Precision)</option>
              <option value="Ollama Custom">Ollama Custom Endpoint</option>
            </select>
          </div>

          {/* 6. Transcription */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-neutral-400 flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-teal-400" />
              <span>Transcription</span>
            </label>
            <select
              value={settings.transcription || "Whisper"}
              onChange={(e) => updateSetting("transcription", e.target.value)}
              disabled={isProcessing}
              className="w-full px-3 py-2 bg-neutral-900 border border-neutral-750 rounded-xl text-xs text-neutral-200 focus:border-amber-500/80 outline-none transition-colors font-mono disabled:opacity-60"
            >
              <option value="Whisper">Whisper (faster-whisper Medium)</option>
              <option value="Whisper Large">Whisper Large-v3</option>
              <option value="Whisper Small">Whisper Small (Low VRAM)</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
