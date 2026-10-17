export const PIPELINE_STEPS = [
  {
    id: "download",
    stepNumber: "01",
    label: "Downloading source",
    detail: "Fetching audio from YouTube or the uploaded file"
  },
  {
    id: "transcribe",
    stepNumber: "02",
    label: "Transcribing",
    detail: "Running OpenAI Whisper with word-level timestamps"
  },
  {
    id: "moments",
    stepNumber: "03",
    label: "Finding best moments",
    detail: "Prompting Qwen 2.5 via Ollama for viral highlights"
  },
  {
    id: "video",
    stepNumber: "04",
    label: "Preparing video",
    detail: "Downloading or copying the full source video"
  },
  {
    id: "cut",
    stepNumber: "05",
    label: "Cutting clips",
    detail: "Extracting highlight segments with FFmpeg"
  },
  {
    id: "reframe",
    stepNumber: "06",
    label: "Smart reframing",
    detail: "Face-tracked 9:16 crop with smooth camera movement"
  },
  {
    id: "captions",
    stepNumber: "07",
    label: "Adding captions",
    detail: "Burning word-by-word captions into the vertical clips"
  }
];

const STEP_INDEX = Object.fromEntries(PIPELINE_STEPS.map((step, index) => [step.id, index]));

async function readSSE(response, onEvent) {
  if (!response.body) {
    throw new Error("This browser cannot stream generation progress.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;
  let streamError = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      let event = "message";
      const dataLines = [];
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      if (!dataLines.length) continue;
      const payload = JSON.parse(dataLines.join("\n"));
      if (event === "complete") {
        finalResult = payload;
      } else if (event === "error") {
        streamError = payload.message || "Clip generation failed.";
      }
      onEvent(event, payload);
    }
  }

  if (streamError) {
    throw new Error(streamError);
  }
  if (!finalResult) {
    throw new Error("The generator stopped before finishing. Is the Clipreator API running?");
  }
  return finalResult;
}

/**
 * Runs the real Clipreator pipeline through the local Go API.
 */
export async function generateClips({ source, sourceType, settings = {}, file }, onStepProgress) {
  const bodyPayload = {
    url: sourceType === "youtube" ? source : "",
    smartReframing: Boolean(settings.smartReframing),
    captions: Boolean(settings.captions),
    reframeMode: settings.smartReframing ? "auto" : "center",
    clipCount: settings.clipCount || "Auto",
    reframeWidth: 1080,
    reframeHeight: 1920,
    transcribeDevice: settings.transcribeDevice || settings.device || "GPU (CUDA / MPS)",
    transcribeCompute: settings.transcribeCompute || settings.computeType || "float16"
  };

  let response;
  try {
    if (sourceType === "upload" && file) {
      const form = new FormData();
      form.append("file", file);
      form.append("url", bodyPayload.url);
      form.append("smartReframing", String(bodyPayload.smartReframing));
      form.append("captions", String(bodyPayload.captions));
      form.append("reframeMode", bodyPayload.reframeMode);
      form.append("clipCount", bodyPayload.clipCount);
      form.append("reframeWidth", String(bodyPayload.reframeWidth));
      form.append("reframeHeight", String(bodyPayload.reframeHeight));
      form.append("transcribeDevice", bodyPayload.transcribeDevice);
      form.append("transcribeCompute", bodyPayload.transcribeCompute);
      response = await fetch("/api/generate", {
        method: "POST",
        headers: {
          "Accept": "text/event-stream",
        },
        body: form
      });
    } else {
      response = await fetch("/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: JSON.stringify(bodyPayload)
      });
    }
  } catch {
    throw new Error(
      "Could not reach the Clipreator API. Start it with: ./bin/clipreator -serve"
    );
  }

  if (response.status === 409) {
    throw new Error("A generation job is already running.");
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok && !contentType.includes("text/event-stream")) {
    let message = `Generator returned HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data.error) message = data.error;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }

  return readSSE(response, (event, payload) => {
    if (event !== "step" || !onStepProgress) return;
    const stepIndex = STEP_INDEX[payload.stepId] ?? payload.stepIndex ?? 0;
    onStepProgress({
      stepIndex,
      stepId: payload.stepId,
      label: payload.label,
      status: payload.status,
      detail: payload.detail,
      totalSteps: PIPELINE_STEPS.length,
      currentStep: stepIndex + 1
    });
  });
}

export function downloadClip(clip) {
  if (!clip?.videoUrl) return;
  const link = document.createElement("a");
  link.href = clip.videoUrl;
  link.download = clip.filename || `clip_${clip.clipNumber || clip.id}.mp4`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export async function downloadAllClips(clips) {
  for (const clip of clips || []) {
    downloadClip(clip);
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}
