import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Toast from "./components/Toast";
import ClipGenerator from "./pages/ClipGenerator";
import StoryStudio from "./pages/StoryStudio";
import Projects from "./pages/Projects";
import Settings from "./pages/Settings";
import { DEFAULT_SETTINGS } from "./data/mockClips";

export default function App() {
  const [activePage, setActivePage] = useState("generator");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [toast, setToast] = useState(null);
  const [appSettings, setAppSettings] = useState(DEFAULT_SETTINGS);

  const showToast = (toastObj) => {
    setToast(toastObj);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-neutral-950 text-neutral-100 select-none font-sans">
      {/* Persistent Left Sidebar */}
      <Sidebar
        activePage={activePage}
        onNavigate={(pageId) => setActivePage(pageId)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Page Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {activePage === "generator" && (
          <ClipGenerator onShowToast={showToast} aiSettings={appSettings.ai} />
        )}

        {activePage === "story-studio" && (
          <StoryStudio />
        )}

        {activePage === "projects" && (
          <Projects onShowToast={showToast} />
        )}

        {activePage === "settings" && (
          <Settings
            onShowToast={showToast}
            settings={appSettings}
            setSettings={setAppSettings}
          />
        )}

        {/* Global Toast Notification */}
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
