import { Film, BookOpen, FolderGit2, Settings, Sparkles, Cpu, ChevronLeft, ChevronRight } from "lucide-react";

export default function Sidebar({
  activePage,
  onNavigate,
  collapsed,
  onToggleCollapse
}) {
  const navItems = [
    {
      id: "generator",
      label: "Clip Generator",
      icon: Film,
      badge: null
    },
    {
      id: "story-studio",
      label: "Story Studio",
      icon: BookOpen,
      badge: "Coming Soon",
      isComingSoon: true
    },
    {
      id: "projects",
      label: "Projects",
      icon: FolderGit2,
      badge: null
    },
    {
      id: "settings",
      label: "Settings",
      icon: Settings,
      badge: null
    }
  ];

  return (
    <aside
      className={`relative flex flex-col bg-neutral-950 border-r border-neutral-800/80 transition-all duration-300 ease-in-out shrink-0 select-none z-20 ${
        collapsed ? "w-18" : "w-64"
      }`}
    >
      {/* App Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-neutral-850">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-lg shadow-amber-950/40 shrink-0 border border-amber-400/20">
            <Film className="w-5 h-5 text-neutral-950 stroke-[2.2]" />
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="font-bold text-sm tracking-widest text-neutral-100 flex items-center gap-1.5 font-mono">
                CLIPREATOR
                <span className="text-[10px] font-sans px-1.5 py-0.2 bg-neutral-800 text-amber-400 rounded border border-neutral-700">CLI</span>
              </span>
              <span className="text-[10px] text-neutral-400 tracking-wide">
                Local AI Video Studio
              </span>
            </div>
          )}
        </div>

        {/* Toggle Collapse Button */}
        <button
          onClick={onToggleCollapse}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="hidden md:flex p-1.5 rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-850 transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 group relative ${
                isActive
                  ? "bg-neutral-850 text-neutral-100 border border-neutral-700/60 shadow-sm"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/80"
              }`}
            >
              <Icon
                className={`w-4 h-4 shrink-0 transition-colors ${
                  isActive
                    ? "text-amber-400"
                    : "text-neutral-400 group-hover:text-neutral-200"
                }`}
              />

              {!collapsed && (
                <div className="flex-1 flex items-center justify-between text-left truncate">
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 font-mono border border-neutral-750">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}

              {/* Active Indicator Bar */}
              {isActive && (
                <div className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-amber-500 rounded-r-full" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Local AI Status Card (Informational UI) */}
      <div className="p-3 border-t border-neutral-850">
        {collapsed ? (
          <div
            className="flex flex-col items-center justify-center p-2 rounded-lg bg-neutral-900/60 border border-neutral-800 text-center"
            title="Local AI Active: Qwen 2.5 & Whisper"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse mb-1" />
            <Cpu className="w-3.5 h-3.5 text-neutral-400" />
          </div>
        ) : (
          <div className="p-3 rounded-lg bg-neutral-900/60 border border-neutral-800/80">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
              <span className="text-xs font-semibold tracking-wide text-neutral-200 uppercase text-[10px]">
                Local AI Engine
              </span>
            </div>

            <div className="space-y-1 text-[11px] text-neutral-400 font-mono pl-4">
              <div className="flex items-center justify-between">
                <span>LLM:</span>
                <span className="text-neutral-300 font-medium">Qwen 2.5</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Audio:</span>
                <span className="text-neutral-300 font-medium">Whisper</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-emerald-400/90 pt-1 border-t border-neutral-800/60">
                <span>Device:</span>
                <span>GPU / CUDA</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
