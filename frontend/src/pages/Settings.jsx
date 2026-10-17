import { useState } from "react";
import Header from "../components/Header";
import { DEFAULT_SETTINGS } from "../data/mockClips";
import {
  Cpu,
  Video,
  HardDrive,
  Save,
  RotateCcw,
  Sparkles,
  Sliders,
  CheckCircle2,
  Folder
} from "lucide-react";

export default function Settings({ onShowToast, settings, setSettings }) {
  const [isSaved, setIsSaved] = useState(false);

  const localSettings = settings ?? DEFAULT_SETTINGS;
  const localSetSettings = setSettings ?? (() => {});

  const handleSave = () => {
    setIsSaved(true);
    onShowToast?.({
      type: "success",
      message: "Configuration saved to ~/.config/clipreator/config.yaml"
    });
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleReset = () => {
    localSetSettings(DEFAULT_SETTINGS);
    onShowToast?.({
      type: "info",
      message: "Settings reset to defaults."
    });
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-neutral-950 overflow-y-auto">
      <Header
        title="Settings"
        subtitle="Configure local AI inference engine, video rendering, and output directories."
      />

      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-4xl w-full mx-auto space-y-6">
        {/* Section 1: AI Engine */}
        <section className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 space-y-5">
          <div className="flex items-center gap-2.5 pb-4 border-b border-neutral-800">
            <Cpu className="w-5 h-5 text-amber-400" />
            <div>
              <h3 className="text-sm font-semibold text-neutral-100">
                AI Engine & Models
              </h3>
              <p className="text-xs text-neutral-400">
                Local LLM and speech recognition model preferences.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Highlight Detection Model
              </label>
              <select
                value={localSettings.ai.model}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    ai: { ...localSettings.ai, model: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="Qwen 2.5 (7B Instruct)">Qwen 2.5 (7B Instruct - Default)</option>
                <option value="Qwen 2.5 (14B Instruct)">Qwen 2.5 (14B Instruct - High Accuracy)</option>
                <option value="Llama 3.2 (3B)">Llama 3.2 (3B - Fast)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Audio Transcription Backend
              </label>
              <select
                value={localSettings.ai.transcriptionModel}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    ai: { ...localSettings.ai, transcriptionModel: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="faster-whisper Medium">faster-whisper Medium (Recommended)</option>
                <option value="faster-whisper Large-v3">faster-whisper Large-v3</option>
                <option value="whisper.cpp (Small)">whisper.cpp (Small - Low Resource)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Hardware Acceleration
              </label>
              <select
                value={localSettings.ai.device}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    ai: { ...localSettings.ai, device: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="GPU (CUDA / MPS)">GPU (CUDA / MPS Acceleration)</option>
                <option value="CPU (Multi-threaded)">CPU (Fallback)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Quantization / Compute Type
              </label>
              <select
                value={localSettings.ai.computeType}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    ai: { ...localSettings.ai, computeType: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="float16">float16 (Optimal speed & quality)</option>
                <option value="int8_float16">int8_float16 (Balanced - Low VRAM)</option>
                <option value="int8">int8 (Minimum VRAM)</option>
                <option value="float32">float32 (Full precision)</option>
              </select>
            </div>
          </div>
        </section>

        {/* Section 2: Video & Reframing */}
        <section className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 space-y-5">
          <div className="flex items-center gap-2.5 pb-4 border-b border-neutral-800">
            <Video className="w-5 h-5 text-blue-400" />
            <div>
              <h3 className="text-sm font-semibold text-neutral-100">
                Video & Reframing
              </h3>
              <p className="text-xs text-neutral-400">
                Default crop ratios, subtitle styling, and camera tracking rules.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Default Aspect Ratio
              </label>
              <select
                value={localSettings.video.aspectRatio}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    video: { ...localSettings.video, aspectRatio: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="9:16">9:16 Vertical (Shorts / Reels / TikTok)</option>
                <option value="1:1">1:1 Square</option>
                <option value="16:9">16:9 Landscape</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Captions
              </label>
              <select
                value={localSettings.video.captionsEnabled ? "Enabled" : "Disabled"}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    video: {
                      ...localSettings.video,
                      captionsEnabled: e.target.value === "Enabled"
                    }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="Enabled">Enabled (Burn into video)</option>
                <option value="Disabled">Disabled</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Smart Reframing
              </label>
              <select
                value={localSettings.video.smartReframing ? "Enabled" : "Disabled"}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    video: {
                      ...localSettings.video,
                      smartReframing: e.target.value === "Enabled"
                    }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="Enabled">Enabled (Preserve camera intent + speaker)</option>
                <option value="Disabled">Disabled (Static crop)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">
                Subtitle Style Preset
              </label>
              <select
                value={localSettings.video.captionPreset}
                onChange={(e) =>
                  localSetSettings({
                    ...localSettings,
                    video: { ...localSettings.video, captionPreset: e.target.value }
                  })
                }
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-750 rounded-xl text-xs text-neutral-200 outline-none focus:border-amber-500/80 font-mono"
              >
                <option value="Bold Yellow Word-by-Word">Bold Yellow Word-by-Word</option>
                <option value="Clean Minimalist White">Clean Minimalist White</option>
                <option value="Cyber Neon Green">Cyber Neon Green</option>
              </select>
            </div>
          </div>
        </section>

        {/* Section 3: Storage & Cache */}
        <section className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-2.5 pb-4 border-b border-neutral-800">
            <HardDrive className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="text-sm font-semibold text-neutral-100">
                Storage & Cache
              </h3>
              <p className="text-xs text-neutral-400">
                Disk cache paths and default clip export location.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-neutral-400">
                Export Output Directory
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={localSettings.storage.outputDir}
                  readOnly
                  className="flex-1 px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs font-mono text-neutral-300"
                />
                <button
                  type="button"
                  onClick={() =>
                    onShowToast?.({
                      type: "info",
                      message: "Directory selector will be linked to native file dialog in desktop build."
                    })
                  }
                  className="px-3 py-2 bg-neutral-800 hover:bg-neutral-750 text-neutral-300 rounded-xl text-xs flex items-center gap-1.5 border border-neutral-750 transition-colors"
                >
                  <Folder className="w-3.5 h-3.5" />
                  <span>Browse</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-neutral-400 hover:text-neutral-200 text-xs font-medium transition-colors hover:bg-neutral-850"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset to Defaults</span>
          </button>

          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-semibold shadow-lg shadow-amber-950/40 transition-all cursor-pointer"
          >
            {isSaved ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Saved!</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Save Settings</span>
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
}
