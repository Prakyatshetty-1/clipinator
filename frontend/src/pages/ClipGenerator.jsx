import { useState, useEffect } from "react";
import Header from "../components/Header";
import SourceInput from "../components/SourceInput";
import GenerationSettings from "../components/GenerationSettings";
import ProcessingPipeline from "../components/ProcessingPipeline";
import ClipGrid from "../components/ClipGrid";
import EmptyState from "../components/EmptyState";
import VideoPreviewModal from "../components/VideoPreviewModal";
import { generateClips, PIPELINE_STEPS, downloadClip, downloadAllClips } from "../services/clipGenerator";
import { SAMPLE_YOUTUBE_URLS } from "../data/mockClips";

export default function ClipGenerator({ onShowToast, aiSettings }) {
  // Source states
  const [sourceType, setSourceType] = useState("youtube"); // 'youtube' | 'upload'
  const [url, setUrl] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Generation settings
  const [settings, setSettings] = useState({
    clipCount: "Auto",
    aspectRatio: "9:16",
    captions: true,
    smartReframing: true,
    aiModel: "Qwen 2.5",
    transcription: "Whisper",
    device: aiSettings?.device || "GPU (CUDA / MPS)",
    computeType: aiSettings?.computeType || "float16"
  });

  // Pipeline states: 'idle' | 'processing' | 'complete' | 'error'
  const [workflowState, setWorkflowState] = useState("idle");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [generationResult, setGenerationResult] = useState(null);

  // Selected clip for preview modal
  const [previewClip, setPreviewClip] = useState(null);
  const [cachedClips, setCachedClips] = useState(null);

  useEffect(() => {
    fetch("/api/clips")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.clips && data.clips.length > 0) {
          setCachedClips(data);
        }
      })
      .catch(() => {});
  }, []);

  // URL Validation helper
  const validateSource = () => {
    if (sourceType === "youtube") {
      const trimmed = url.trim();
      if (!trimmed) {
        setValidationError("Please enter a valid YouTube URL.");
        return false;
      }
      // Basic check for youtube/youtu.be or url format
      const isLikelyYoutube =
        trimmed.includes("youtube.com") ||
        trimmed.includes("youtu.be") ||
        trimmed.startsWith("http://") ||
        trimmed.startsWith("https://");

      if (!isLikelyYoutube) {
        setValidationError("Please enter a valid YouTube URL (e.g., https://www.youtube.com/watch?v=...)");
        return false;
      }
    } else if (sourceType === "upload") {
      if (!uploadedFile) {
        setValidationError("Please select or drop a video file to proceed.");
        return false;
      }
    }
    setValidationError(null);
    return true;
  };

  const handleStartGeneration = async () => {
    if (!validateSource()) return;

    setWorkflowState("processing");
    setCurrentStepIndex(0);
    setCompletedSteps([]);
    setGenerationResult(null);

    try {
      const activeSource =
        sourceType === "youtube" ? url.trim() : uploadedFile?.name || "local_video.mp4";

      const mergedSettings = {
        ...settings,
        device: aiSettings?.device || settings.device || "GPU (CUDA / MPS)",
        computeType: aiSettings?.computeType || settings.computeType || "float16"
      };

      const result = await generateClips(
        {
          source: activeSource,
          sourceType,
          settings: mergedSettings,
          file: uploadedFile?.rawFile || null
        },
        ({ stepIndex, status }) => {
          if (status === "processing") {
            setCurrentStepIndex(stepIndex);
          } else if (status === "completed") {
            setCompletedSteps((prev) => (prev.includes(stepIndex) ? prev : [...prev, stepIndex]));
          }
        }
      );

      setGenerationResult(result);
      setWorkflowState("complete");
      const count = result.clipsCount || result.clips?.length || 0;
      onShowToast?.({
        type: "success",
        message: `${count} clip${count === 1 ? "" : "s"} generated and ready to preview.`
      });
    } catch (err) {
      console.error("Generation error:", err);
      setWorkflowState("idle");
      setCompletedSteps([]);
      setCurrentStepIndex(0);
      setValidationError(err.message || "Clip generation failed. Is ./bin/clipreator -serve running?");
    }
  };

  // Reset workflow back to idle
  const handleReset = () => {
    setWorkflowState("idle");
    setCurrentStepIndex(0);
    setCompletedSteps([]);
    setGenerationResult(null);
    setUrl("");
    setUploadedFile(null);
    setValidationError(null);
  };

  // Handle Export Clip
  const handleExportClip = (clip) => {
    downloadClip(clip);
    onShowToast?.({
      type: "success",
      message: `Downloading CLIP ${clip.clipNumber || clip.id}`
    });
  };

  const handleExportAll = () => {
    downloadAllClips(generationResult?.clips || []);
    onShowToast?.({
      type: "success",
      message: "Downloading generated clips"
    });
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-neutral-950 overflow-y-auto">
      {/* Persistent Page Header */}
      <Header
        title="Clip Generator"
        subtitle="Turn long videos into engaging short-form clips."
      />

      {/* Main Container */}
      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-6xl w-full mx-auto space-y-6">
        {/* Source Input & Settings (Always visible or in idle state) */}
        {workflowState !== "processing" && workflowState !== "complete" && (
          <div className="space-y-4">
            <SourceInput
              sourceType={sourceType}
              setSourceType={setSourceType}
              url={url}
              setUrl={setUrl}
              uploadedFile={uploadedFile}
              setUploadedFile={setUploadedFile}
              onGenerate={handleStartGeneration}
              isProcessing={workflowState === "processing"}
              validationError={validationError}
              setValidationError={setValidationError}
            />

            <GenerationSettings
              settings={settings}
              setSettings={setSettings}
              isProcessing={workflowState === "processing"}
            />
          </div>
        )}

        {/* Processing State: Pipeline Animation */}
        {workflowState === "processing" && (
          <ProcessingPipeline
            currentStepIndex={currentStepIndex}
            completedSteps={completedSteps}
            isFinished={completedSteps.length === PIPELINE_STEPS.length}
          />
        )}

        {/* Complete State: Generated Clips Grid & Summary */}
        {workflowState === "complete" && generationResult && (
          <ClipGrid
            generationResult={generationResult}
            clips={generationResult.clips}
            onReset={handleReset}
            onPreviewClip={(clip) => setPreviewClip(clip)}
            onExportClip={handleExportClip}
            onExportAll={handleExportAll}
          />
        )}

        {/* Idle Empty State */}
        {workflowState === "idle" && (
          <EmptyState
            cachedClips={cachedClips}
            onViewCached={() => {
              if (cachedClips) {
                setGenerationResult(cachedClips);
                setWorkflowState("complete");
                onShowToast?.({
                  type: "success",
                  message: `Loaded ${cachedClips.clips.length} previously generated clips.`
                });
              }
            }}
            onSampleClick={() => {
              setUrl(SAMPLE_YOUTUBE_URLS[0].url);
              setValidationError(null);
            }}
          />
        )}
      </main>

      {/* Modal Preview */}
      <VideoPreviewModal
        clip={previewClip}
        isOpen={!!previewClip}
        onClose={() => setPreviewClip(null)}
        onExport={handleExportClip}
      />
    </div>
  );
}
