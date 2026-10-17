/**
 * Mock data for Clipreator CLI Frontend Prototype
 * Designed for future compatibility with real backend output:
 * {
 *   status: "completed",
 *   source: "video.mp4",
 *   clips: [...]
 * }
 */

export const SAMPLE_YOUTUBE_URLS = [
  {
    title: "The Joe Rogan Experience #2100 - Physics & Future Tech",
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    duration: "2:45:12",
    channel: "PowerfulJRE"
  },
  {
    title: "Lex Fridman Podcast #420 - Deep Learning Architecture",
    url: "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",
    duration: "3:12:08",
    channel: "Lex Fridman"
  },
  {
    title: "Huberman Lab - Optimize Your Focus and Dopamine",
    url: "https://www.youtube.com/watch?v=L_LUpnjgPso",
    duration: "1:58:30",
    channel: "Andrew Huberman"
  }
];

export const MOCK_GENERATED_CLIPS = [
  {
    id: 1,
    clipNumber: "01",
    title: "The Moment Nobody Expected",
    subtitle: "When the unexpected truth about neural networks was revealed",
    transcriptSnippet: "We spent five months training on raw data, and suddenly at step 40,000 the model began reasoning in reverse. Nobody in the lab could explain it.",
    duration: 42,
    durationFormatted: "00:42",
    score: 95,
    viralHook: "Mind-blowing revelation",
    speakers: ["Speaker A (Host)", "Speaker B (Researcher)"],
    reframingMode: "Speaker tracking + Focus on diagram",
    captionsEnabled: true,
    accentColor: "from-amber-600/30 to-amber-950/80",
    tags: ["High Energy", "Viral Hook", "Technical"],
    aspectRatio: "9:16",
    videoUrl: null, // Will use interactive canvas/animated preview
    thumbnailUrl: null
  },
  {
    id: 2,
    clipNumber: "02",
    title: "The Secret Behind 10x Speedup",
    subtitle: "Why quantizing weights changed everything for local AI",
    transcriptSnippet: "If you don't quantize to 4-bit, you're literally paying 8 times more memory bandwidth for zero noticeable perplexity gain.",
    duration: 34,
    durationFormatted: "00:34",
    score: 89,
    viralHook: "Contrarian opinion",
    speakers: ["Speaker B (Engineer)"],
    reframingMode: "Speaker tracking",
    captionsEnabled: true,
    accentColor: "from-emerald-600/30 to-emerald-950/80",
    tags: ["Insight", "Fast Paced", "Actionable"],
    aspectRatio: "9:16",
    videoUrl: null,
    thumbnailUrl: null
  },
  {
    id: 3,
    clipNumber: "03",
    title: "This Decision Almost Killed The Project",
    subtitle: "A candid breakdown of their biggest production mistake",
    transcriptSnippet: "We pushed the update on Friday at 6 PM. Within ten minutes, three thousand GPU nodes crashed simultaneously. My phone wouldn't stop ringing.",
    duration: 58,
    durationFormatted: "00:58",
    score: 92,
    viralHook: "Dramatic storytelling",
    speakers: ["Speaker A (Founder)"],
    reframingMode: "Composition intent preserved",
    captionsEnabled: true,
    accentColor: "from-blue-600/30 to-blue-950/80",
    tags: ["Story", "Suspense", "Lesson"],
    aspectRatio: "9:16",
    videoUrl: null,
    thumbnailUrl: null
  }
];

export const MOCK_PROJECTS = [
  {
    id: "proj-101",
    name: "Lex Fridman #420 - Deep Learning Architecture",
    sourceType: "youtube",
    source: "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",
    clipCount: 4,
    totalDuration: "3:12:08",
    date: "Today, 11:42 AM",
    status: "Completed",
    topScore: 96,
    clips: MOCK_GENERATED_CLIPS
  },
  {
    id: "proj-102",
    name: "Huberman Lab - Focus & Neurotransmitters",
    sourceType: "youtube",
    source: "https://www.youtube.com/watch?v=L_LUpnjgPso",
    clipCount: 3,
    totalDuration: "1:58:30",
    date: "Yesterday, 4:15 PM",
    status: "Completed",
    topScore: 92,
    clips: MOCK_GENERATED_CLIPS.slice(0, 2)
  },
  {
    id: "proj-103",
    name: "Raw Footage - Indie Game Devlog #04",
    sourceType: "upload",
    source: "indie_devlog_v4_raw_4k.mp4",
    clipCount: 5,
    totalDuration: "42:15",
    date: "Oct 05, 2026",
    status: "Completed",
    topScore: 94,
    clips: MOCK_GENERATED_CLIPS
  },
  {
    id: "proj-104",
    name: "Keynote - Autonomous Agents Summit 2026",
    sourceType: "youtube",
    source: "https://www.youtube.com/watch?v=sample-keynote",
    clipCount: 2,
    totalDuration: "1:15:00",
    date: "Oct 02, 2026",
    status: "Archived",
    topScore: 88,
    clips: MOCK_GENERATED_CLIPS.slice(1, 3)
  }
];

export const DEFAULT_SETTINGS = {
  ai: {
    model: "Qwen 2.5 (7B Instruct)",
    transcriptionModel: "faster-whisper Medium",
    device: "GPU (CUDA / MPS)",
    computeType: "float16",
    promptStyle: "High-Virality Short Clips (TikTok / Reels / Shorts)"
  },
  video: {
    aspectRatio: "9:16",
    captionsEnabled: true,
    smartReframing: true,
    captionPreset: "Bold Yellow Word-by-Word",
    reframeSensitivity: "Balanced (Speaker + Camera Intent)",
    exportFormat: "MP4 (H.264 / AAC)",
    fps: "60 FPS",
    bitrate: "16 Mbps"
  },
  storage: {
    cacheDir: "~/.cache/clipreator",
    outputDir: "~/Videos/Clipreator/Exports",
    maxParallelTasks: 2
  }
};
