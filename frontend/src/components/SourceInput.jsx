import { useState, useRef } from "react";
import { Upload, Sparkles, FileVideo, AlertCircle, ArrowRight, X, Play } from "lucide-react";
import { SAMPLE_YOUTUBE_URLS } from "../data/mockClips";

function YoutubeIcon({ className = "w-4 h-4" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
    </svg>
  );
}

export default function SourceInput({
  sourceType,
  setSourceType,
  url,
  setUrl,
  uploadedFile,
  setUploadedFile,
  onGenerate,
  isProcessing,
  validationError,
  setValidationError
}) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !isProcessing) {
      e.preventDefault();
      onGenerate();
    }
  };

  const handleSelectSample = (sampleUrl) => {
    setUrl(sampleUrl);
    setValidationError(null);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile({
        name: file.name,
        size: (file.size / (1024 * 1024)).toFixed(1) + " MB",
        type: file.type || "video/mp4",
        rawFile: file
      });
      setValidationError(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setUploadedFile({
        name: file.name,
        size: (file.size / (1024 * 1024)).toFixed(1) + " MB",
        type: file.type || "video/mp4",
        rawFile: file
      });
      setValidationError(null);
    }
  };

  const canGenerate =
    !isProcessing &&
    ((sourceType === "youtube" && url.trim().length > 0) ||
     (sourceType === "upload" && uploadedFile !== null));

  return (
    <div className="bg-neutral-900/70 border border-neutral-800/90 rounded-2xl p-5 lg:p-6 shadow-xl backdrop-blur-sm transition-all duration-200">
      {/* Source Selection Tabs */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-neutral-800/70">
        <div className="flex items-center gap-2 p-1 bg-neutral-950/80 rounded-xl border border-neutral-800">
          <button
            type="button"
            onClick={() => {
              setSourceType("youtube");
              setValidationError(null);
            }}
            disabled={isProcessing}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
              sourceType === "youtube"
                ? "bg-neutral-800 text-neutral-100 shadow-sm border border-neutral-700/80"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/50"
            }`}
          >
            <YoutubeIcon className="w-4 h-4 text-rose-500" />
            <span>YouTube URL</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setSourceType("upload");
              setValidationError(null);
            }}
            disabled={isProcessing}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
              sourceType === "upload"
                ? "bg-neutral-800 text-neutral-100 shadow-sm border border-neutral-700/80"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/50"
            }`}
          >
            <Upload className="w-4 h-4 text-amber-400" />
            <span>Upload Video</span>
          </button>
        </div>

        {/* Quick sample chips (for easy testing) */}
        {sourceType === "youtube" && (
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-[11px] text-neutral-500">Quick Test:</span>
            <button
              type="button"
              onClick={() => handleSelectSample(SAMPLE_YOUTUBE_URLS[0].url)}
              disabled={isProcessing}
              className="text-[11px] font-mono px-2 py-1 bg-neutral-850 hover:bg-neutral-800 text-neutral-300 hover:text-amber-400 rounded border border-neutral-750 transition-colors"
            >
              Podcast Sample
            </button>
            <button
              type="button"
              onClick={() => handleSelectSample(SAMPLE_YOUTUBE_URLS[2].url)}
              disabled={isProcessing}
              className="text-[11px] font-mono px-2 py-1 bg-neutral-850 hover:bg-neutral-800 text-neutral-300 hover:text-amber-400 rounded border border-neutral-750 transition-colors"
            >
              Talk Show
            </button>
          </div>
        )}
      </div>

      {/* Tab 1: YouTube URL Input */}
      {sourceType === "youtube" && (
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-500">
                <YoutubeIcon className="w-4 h-4 text-neutral-400" />
              </div>
              <input
                type="url"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                onKeyDown={handleKeyDown}
                disabled={isProcessing}
                placeholder="Paste a YouTube URL... (e.g. https://www.youtube.com/watch?v=...)"
                className="w-full pl-10 pr-10 py-3.5 bg-neutral-950/90 border border-neutral-750 focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 rounded-xl text-neutral-100 placeholder:text-neutral-500 text-sm transition-all outline-none font-mono tracking-tight disabled:opacity-60"
              />
              {url && !isProcessing && (
                <button
                  type="button"
                  onClick={() => {
                    setUrl("");
                    setValidationError(null);
                  }}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-neutral-500 hover:text-neutral-300"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={onGenerate}
              disabled={!canGenerate}
              className={`px-6 py-3.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition-all duration-200 select-none shrink-0 ${
                canGenerate
                  ? "bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-lg shadow-amber-950/50 hover:shadow-amber-500/20 active:scale-[0.98] cursor-pointer font-semibold"
                  : "bg-neutral-800 text-neutral-500 cursor-not-allowed border border-neutral-750"
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Generate Clips</span>
            </button>
          </div>

          <div className="flex items-center justify-between text-[11px] text-neutral-500 px-1">
            <span>Supports standard YouTube links, Shorts, & Livestream recordings</span>
            <span className="hidden sm:inline font-mono">Press [Enter] to submit</span>
          </div>
        </div>
      )}

      {/* Tab 2: Upload Video Area */}
      {sourceType === "upload" && (
        <div className="space-y-4">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
            className="hidden"
          />

          {!uploadedFile ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
                isDragging
                  ? "border-amber-500 bg-amber-500/5"
                  : "border-neutral-750 hover:border-neutral-600 bg-neutral-950/40 hover:bg-neutral-950/80"
              }`}
            >
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-neutral-850 flex items-center justify-center text-amber-400 border border-neutral-700">
                <Upload className="w-6 h-6" />
              </div>
              <p className="text-sm font-medium text-neutral-200 mb-1">
                Drop a video here
              </p>
              <p className="text-xs text-neutral-400 mb-3">
                or <span className="text-amber-400 underline underline-offset-2">browse files</span> from your computer
              </p>
              <p className="text-[11px] text-neutral-500 font-mono">
                MP4, MOV, MKV, or WEBM up to 4GB
              </p>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 bg-neutral-950 border border-neutral-750 rounded-xl gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-neutral-800 flex items-center justify-center text-amber-400 border border-neutral-700 shrink-0">
                  <FileVideo className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-medium text-neutral-200 truncate max-w-xs sm:max-w-md">
                    {uploadedFile.name}
                  </h4>
                  <p className="text-xs text-neutral-400 font-mono">
                    {uploadedFile.size} • {uploadedFile.type}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto">
                <button
                  type="button"
                  onClick={() => setUploadedFile(null)}
                  disabled={isProcessing}
                  className="px-3 py-2 text-xs text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
                >
                  Change File
                </button>

                <button
                  type="button"
                  onClick={onGenerate}
                  disabled={!canGenerate}
                  className={`px-5 py-2.5 rounded-xl font-medium text-xs flex items-center gap-2 transition-all cursor-pointer ${
                    canGenerate
                      ? "bg-amber-500 hover:bg-amber-400 text-neutral-950 font-semibold shadow-md shadow-amber-950/40"
                      : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate Clips</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Validation Error Alert */}
      {validationError && (
        <div className="mt-4 p-3.5 bg-rose-950/30 border border-rose-800/60 rounded-xl flex items-center justify-between gap-3 text-xs text-rose-300 animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{validationError}</span>
          </div>
          <button
            type="button"
            onClick={() => setValidationError(null)}
            className="text-rose-400 hover:text-rose-200 text-xs font-medium underline underline-offset-2 shrink-0"
          >
            Try Again
          </button>
        </div>
      )}
    </div>
  );
}
