import { useState, useEffect } from "react";
import Header from "../components/Header";
import VideoPreviewModal from "../components/VideoPreviewModal";
import {
  FolderGit2,
  Film,
  Calendar,
  Clock,
  Sparkles,
  ExternalLink,
  Play,
  CheckCircle2,
  Search,
  ChevronRight,
  Download,
  Trash2,
  Flame
} from "lucide-react";

export default function Projects({ onShowToast }) {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [previewClip, setPreviewClip] = useState(null);

  useEffect(() => {
    fetch("/api/clips")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.clips && data.clips.length > 0) {
          const realProject = {
            id: "real-latest-run",
            name: data.clips[0]?.title || "Latest Pipeline Clips",
            source: data.source || "https://youtu.be/eNa_HmAibUk",
            sourceType: data.sourceType || "youtube",
            date: "Today (Real GPU)",
            clipCount: data.clips.length,
            totalDuration: data.processingTime || "02:15",
            topScore: Math.max(...data.clips.map((c) => c.score || 95)),
            status: "Completed",
            clips: data.clips
          };
          setProjects([realProject]);
          setSelectedProject(realProject);
        } else {
          setProjects([]);
          setSelectedProject(null);
        }
      })
      .catch(() => {
        setProjects([]);
        setSelectedProject(null);
      });
  }, []);

  const filteredProjects = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.source.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleExportProject = (proj) => {
    onShowToast?.({
      type: "success",
      message: `Exported ${proj.clipCount} clips from "${proj.name}" to ~/Videos`
    });
  };

  const handleDeleteProject = (projId) => {
    setProjects((prev) => prev.filter((p) => p.id !== projId));
    if (selectedProject?.id === projId) {
      setSelectedProject(null);
    }
    onShowToast?.({
      type: "info",
      message: "Project removed from history."
    });
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-neutral-950 overflow-y-auto">
      <Header
        title="Projects"
        subtitle="Manage previous AI clipping batches and extracted vertical reels."
      />

      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-6xl w-full mx-auto space-y-6">
        {/* Top Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search previous clipping projects..."
              className="w-full pl-10 pr-4 py-2.5 bg-neutral-900 border border-neutral-800 rounded-xl text-xs text-neutral-200 placeholder:text-neutral-500 focus:border-amber-500/80 outline-none transition-colors"
            />
          </div>

          <div className="text-xs font-mono text-neutral-400">
            Total Projects: <span className="text-neutral-200 font-semibold">{projects.length}</span>
          </div>
        </div>

        {/* Project Master-Detail Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Projects List (Left Column) */}
          <div className="lg:col-span-5 space-y-3">
            {filteredProjects.map((proj) => {
              const isSelected = selectedProject?.id === proj.id;

              return (
                <div
                  key={proj.id}
                  onClick={() => setSelectedProject(proj)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? "bg-neutral-850/90 border-amber-500/60 shadow-lg shadow-neutral-950/50"
                      : "bg-neutral-900/50 hover:bg-neutral-900 border-neutral-800 hover:border-neutral-700/80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-300 border border-neutral-750">
                          {proj.sourceType === "youtube" ? "YouTube" : "Local File"}
                        </span>
                        <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          {proj.status}
                        </span>
                      </div>

                      <h4 className="text-sm font-semibold text-neutral-100 truncate mt-1">
                        {proj.name}
                      </h4>

                      <p className="text-[11px] text-neutral-500 font-mono truncate">
                        {proj.source}
                      </p>
                    </div>

                    <ChevronRight
                      className={`w-4 h-4 shrink-0 transition-transform mt-1 ${
                        isSelected ? "text-amber-400 translate-x-0.5" : "text-neutral-600"
                      }`}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono text-neutral-400 pt-3 mt-3 border-t border-neutral-800/80">
                    <div className="flex items-center gap-1.5">
                      <Film className="w-3 h-3 text-amber-400" />
                      <span>{proj.clipCount} clips</span>
                    </div>

                    <div className="flex items-center gap-1.5 text-neutral-500">
                      <Calendar className="w-3 h-3" />
                      <span>{proj.date}</span>
                    </div>
                  </div>
                </div>
              );
            })}

            {filteredProjects.length === 0 && (
              <div className="p-8 text-center text-xs text-neutral-500 border border-dashed border-neutral-800 rounded-xl">
                {searchQuery
                  ? "No projects matched your search."
                  : "No clipping projects yet. Run Clip Generator to create reels."}
              </div>
            )}
          </div>

          {/* Project Details & Clips Preview (Right Column) */}
          <div className="lg:col-span-7 bg-neutral-900/60 border border-neutral-800 rounded-2xl p-5 lg:p-6 space-y-5">
            {selectedProject ? (
              <>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-800">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400">
                      Project Details
                    </span>
                    <h3 className="text-base font-bold text-neutral-100 mt-0.5">
                      {selectedProject.name}
                    </h3>
                    <p className="text-xs text-neutral-400 font-mono mt-0.5 truncate max-w-md">
                      {selectedProject.source}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleExportProject(selectedProject)}
                      className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium flex items-center gap-1.5 transition-colors border border-neutral-700/80"
                    >
                      <Download className="w-3.5 h-3.5 text-amber-400" />
                      <span>Export</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleDeleteProject(selectedProject.id)}
                      className="p-1.5 rounded-lg text-neutral-500 hover:text-rose-400 hover:bg-rose-950/20 transition-colors"
                      title="Delete project"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Project Stats Banner */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800">
                    <span className="text-[10px] font-mono text-neutral-500">Clips</span>
                    <p className="text-base font-bold text-neutral-200 mt-0.5">
                      {selectedProject.clipCount}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800">
                    <span className="text-[10px] font-mono text-neutral-500">Source Duration</span>
                    <p className="text-base font-bold text-neutral-200 mt-0.5 font-mono">
                      {selectedProject.totalDuration}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800">
                    <span className="text-[10px] font-mono text-neutral-500">Top Viral Score</span>
                    <p className="text-base font-bold text-emerald-400 mt-0.5 flex items-center gap-1">
                      <Flame className="w-4 h-4" />
                      {selectedProject.topScore}
                    </p>
                  </div>
                </div>

                {/* Clips in Project */}
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-3">
                    Extracted Clips ({selectedProject.clips.length})
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {selectedProject.clips.map((clip) => (
                      <div
                        key={clip.id}
                        className="p-3 rounded-xl bg-neutral-950/80 border border-neutral-800 flex items-center justify-between gap-3 group hover:border-neutral-700 transition-colors"
                      >
                        <div className="min-w-0">
                          <span className="text-[10px] font-mono text-neutral-500">
                            CLIP {clip.clipNumber} • {clip.durationFormatted}
                          </span>
                          <h5 className="text-xs font-medium text-neutral-200 truncate mt-0.5">
                            "{clip.title}"
                          </h5>
                        </div>

                        <button
                          type="button"
                          onClick={() => setPreviewClip(clip)}
                          className="p-2 rounded-lg bg-neutral-850 hover:bg-amber-500 hover:text-neutral-950 text-neutral-300 transition-colors shrink-0"
                          title="Preview clip"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="p-12 text-center text-xs text-neutral-500">
                Select a project from the left to view details and clips.
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Video Preview Modal */}
      <VideoPreviewModal
        clip={previewClip}
        isOpen={!!previewClip}
        onClose={() => setPreviewClip(null)}
        onExport={(clip) =>
          onShowToast?.({
            type: "success",
            message: `Exported CLIP ${clip.clipNumber} to ~/Videos`
          })
        }
      />
    </div>
  );
}
