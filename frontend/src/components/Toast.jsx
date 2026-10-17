import { useEffect } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

export default function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onClose();
    }, 3800);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
    error: <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />,
    info: <Info className="w-4 h-4 text-amber-400 shrink-0" />
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-3 duration-200">
      <div className="flex items-center gap-3 px-4 py-3 bg-neutral-900/95 border border-neutral-700/80 rounded-xl shadow-2xl backdrop-blur-md max-w-md text-sm text-neutral-200">
        {icons[toast.type || "info"]}
        <span className="flex-1 font-medium text-xs sm:text-sm">{toast.message}</span>
        <button
          onClick={onClose}
          className="text-neutral-400 hover:text-neutral-200 transition-colors p-1 -mr-1"
          aria-label="Close notification"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
