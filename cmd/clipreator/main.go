package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/Verifieddanny/clipreator-cli/internal/analyzer"
	"github.com/Verifieddanny/clipreator-cli/internal/captioner"
	"github.com/Verifieddanny/clipreator-cli/internal/cutter"
	"github.com/Verifieddanny/clipreator-cli/internal/reframer"
	"github.com/Verifieddanny/clipreator-cli/internal/transcriber"
)

func main() {
	var url string
	var reframeEnabled bool
	var noReframe bool
	var reframeMode string
	var reframeWidth int
	var reframeHeight int
	var reframeSmoothing float64
	var ollamaModel string

	flag.StringVar(&url, "url", "", "YouTube URL to process")
	flag.BoolVar(&reframeEnabled, "reframe", true, "enable smart 9:16 face-tracked reframing (default true)")
	flag.BoolVar(&noReframe, "no-reframe", false, "disable smart reframing and use a static center crop")
	flag.StringVar(&reframeMode, "reframe-mode", "auto", "reframe mode: auto (face tracking) or center")
	flag.IntVar(&reframeWidth, "reframe-width", 1080, "vertical output width")
	flag.IntVar(&reframeHeight, "reframe-height", 1920, "vertical output height")
	flag.Float64Var(&reframeSmoothing, "reframe-smoothing", 0.03, "camera refocus band as a fraction of frame width (larger = calmer)")
	flag.StringVar(&ollamaModel, "ollama-model", "", "Ollama model name (defaults to qwen2.5:latest)")
	flag.Parse()

	if url == "" {
		fmt.Println("URL is required")
		os.Exit(1)
	}

	if ollamaModel != "" {
		os.Setenv("OLLAMA_MODEL", ollamaModel)
	}

	if noReframe || os.Getenv("CLIPREATOR_REFRAME") == "0" {
		reframeEnabled = false
	}
	reframeMode = strings.ToLower(strings.TrimSpace(reframeMode))
	if reframeMode != "auto" && reframeMode != "center" {
		fmt.Println("reframe-mode must be auto or center")
		os.Exit(1)
	}
	if !reframeEnabled {
		reframeMode = "center"
	}

	workDir := ".clipreator_tmp"

	fmt.Println("📥 Downloading audio...")
	audioPath, err := transcriber.DownloadAudio(url, workDir)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✅ Audio saved to: %s\n\n", audioPath)

	fmt.Println("🎙️ Transcribing with Whisper...")
	transcript, err := transcriber.Transcribe(audioPath, workDir)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("\n✅ Transcription complete! %d segments found\n\n", len(transcript.Segments))

	for i, seg := range transcript.Segments {
		if i < 5 {
			fmt.Printf("[%06.2f -> %06.2f] %s\n", seg.Start, seg.End, seg.Text)
		}
	}
	if len(transcript.Segments) > 5 {
		fmt.Printf("\n... and %d more segments\n", len(transcript.Segments)-5)
	}

	fmt.Println("🧠 Analyzing transcript for viral clips...")
	result, err := analyzer.Analyze(transcript)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("🎬 Found %d potential clips:\n\n", len(result.Clips))
	for i, clip := range result.Clips {
		minutes := int(clip.Start) / 60
		seconds := int(clip.Start) % 60
		endMin := int(clip.End) / 60
		endSec := int(clip.End) % 60
		duration := clip.End - clip.Start

		fmt.Printf("  Clip %d: %s\n", i+1, clip.Title)
		fmt.Printf("  ⏱️  %02d:%02d → %02d:%02d (%.0fs)\n", minutes, seconds, endMin, endSec, duration)
		fmt.Printf("  🎣 Hook: %s\n", clip.Hook)
		fmt.Printf("  🔥 Why: %s\n\n", clip.Why)
	}

	fmt.Println("📥 Downloading full video...")
	videoPath, err := cutter.DownloadVideo(url, workDir)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✅ Video saved to: %s\n\n", videoPath)

	fmt.Println("✂️  Cutting clips...")
	clipPaths, err := cutter.CutClips(videoPath, workDir, result.Clips)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("\n📱 Reframes to 9:16...")
	reframeOpts := reframer.DefaultOptions()
	reframeOpts.Mode = reframeMode
	reframeOpts.Width = reframeWidth
	reframeOpts.Height = reframeHeight
	reframeOpts.RefocusBand = reframeSmoothing
	reframeOpts.WorkDir = workDir
	for i, clipResult := range clipPaths {
		label := "smart face tracking"
		if reframeMode == "center" {
			label = "center crop"
		}
		fmt.Printf("  🎥 Clip %d (%s)...\n", i+1, label)
		if err := reframer.Reframe(clipResult.Path, reframeOpts); err != nil {
			fmt.Printf("    ⚠️  Reframe failed: %v\n", err)
			continue
		}
		fmt.Printf("    ✅ %dx%d ready\n", reframeWidth, reframeHeight)
	}

	fmt.Println("\n💬 Adding captions...")
	clipsDir := filepath.Join(workDir, "clips")
	var finalPaths []string

	for i, clipResult := range clipPaths {
		clip := result.Clips[i]
		fmt.Printf("  💬 Captioning clip %d: %s\n", i+1, clip.Title)

		words := captioner.ExtractWords(transcript, clip.Start, clip.End)
		if len(words) == 0 {
			fmt.Printf("    ⚠️  No word timestamps found, skipping captions\n")
			finalPaths = append(finalPaths, clipResult.Path)
			continue
		}

		words = captioner.RemapWords(words, clipResult.KeptSegments)
		fmt.Printf("    📝 %d words synced to edited timeline\n", len(words))

		captionedPath := filepath.Join(clipsDir, fmt.Sprintf("final_%d.mp4", i+1))
		if err := captioner.BurnCaptions(clipResult.Path, words, captionedPath); err != nil {
			fmt.Printf("    ⚠️  Failed to burn captions: %v\n", err)
			finalPaths = append(finalPaths, clipResult.Path)
			continue
		}

		os.Remove(clipResult.Path)
		os.Rename(captionedPath, clipResult.Path)
		fmt.Printf("    ✅ Captions synced!\n")
		finalPaths = append(finalPaths, clipResult.Path)
	}

	fmt.Printf("\n🎉 Done! %d clips ready:\n", len(clipPaths))
	for _, p := range clipPaths {
		fmt.Printf("  📎 %s\n", p.Path)
	}

}
