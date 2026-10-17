package pipeline

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/Verifieddanny/clipreator-cli/internal/analyzer"
	"github.com/Verifieddanny/clipreator-cli/internal/captioner"
	"github.com/Verifieddanny/clipreator-cli/internal/cutter"
	"github.com/Verifieddanny/clipreator-cli/internal/reframer"
	"github.com/Verifieddanny/clipreator-cli/internal/transcriber"
)

type Progress struct {
	StepID      string `json:"stepId"`
	StepIndex   int    `json:"stepIndex"`
	Label       string `json:"label"`
	Status      string `json:"status"`
	Detail      string `json:"detail,omitempty"`
	TotalSteps  int    `json:"totalSteps"`
	CurrentStep int    `json:"currentStep"`
}

type ResultClip struct {
	ID                int      `json:"id"`
	ClipNumber        string   `json:"clipNumber"`
	Title             string   `json:"title"`
	Subtitle          string   `json:"subtitle"`
	TranscriptSnippet string   `json:"transcriptSnippet"`
	Duration          float64  `json:"duration"`
	DurationFormatted string   `json:"durationFormatted"`
	Path              string   `json:"path"`
	Filename          string   `json:"filename"`
	VideoURL          string   `json:"videoUrl"`
	CaptionsEnabled   bool     `json:"captionsEnabled"`
	ReframingMode     string   `json:"reframingMode"`
	AspectRatio       string   `json:"aspectRatio"`
	Score             int      `json:"score"`
	Tags              []string `json:"tags"`
	AccentColor       string   `json:"accentColor"`
	Start             float64  `json:"start"`
	End               float64  `json:"end"`
	Hook              string   `json:"hook"`
	Why               string   `json:"why"`
}

type Result struct {
	Status         string       `json:"status"`
	Source         string       `json:"source"`
	SourceType     string       `json:"sourceType"`
	ProcessingTime string       `json:"processingTime"`
	ClipsCount     int          `json:"clipsCount"`
	Clips          []ResultClip `json:"clips"`
	Timestamp      string       `json:"timestamp"`
}

type Options struct {
	URL                 string
	LocalVideo          string
	WorkDir             string
	ReframeEnabled      bool
	ReframeMode         string
	ReframeWidth        int
	ReframeHeight       int
	ReframeSmoothing    float64
	Captions            bool
	ClipCount           int
	ForceRefresh        bool
	TranscribeDevice    string
	TranscribeCompute   string
	DebugReframe        bool
	OnProgress          func(Progress)
}

var Steps = []struct {
	ID    string
	Label string
}{
	{"download", "Downloading source"},
	{"transcribe", "Transcribing"},
	{"moments", "Finding best moments"},
	{"video", "Preparing video"},
	{"cut", "Cutting clips"},
	{"reframe", "Smart reframing"},
	{"captions", "Adding captions"},
}

func Run(opts Options) (*Result, error) {
	start := time.Now()
	if opts.WorkDir == "" {
		opts.WorkDir = ".clipreator_tmp"
	}
	if opts.ReframeMode == "" {
		opts.ReframeMode = "auto"
	}
	if !opts.ReframeEnabled {
		opts.ReframeMode = "center"
	}
	if opts.ReframeWidth <= 0 {
		opts.ReframeWidth = 1080
	}
	if opts.ReframeHeight <= 0 {
		opts.ReframeHeight = 1920
	}
	if err := os.MkdirAll(opts.WorkDir, 0755); err != nil {
		return nil, err
	}

	source := opts.URL
	sourceType := "youtube"
	if opts.LocalVideo != "" {
		source = filepath.Base(opts.LocalVideo)
		sourceType = "upload"
	}

	emit := func(index int, status, detail string) {
		if opts.OnProgress == nil || index < 0 || index >= len(Steps) {
			return
		}
		step := Steps[index]
		opts.OnProgress(Progress{
			StepID:      step.ID,
			StepIndex:   index,
			Label:       step.Label,
			Status:      status,
			Detail:      detail,
			TotalSteps:  len(Steps),
			CurrentStep: index + 1,
		})
	}

	if opts.ForceRefresh {
		_ = os.Remove(filepath.Join(opts.WorkDir, "audio.mp3"))
		_ = os.Remove(filepath.Join(opts.WorkDir, "video.mp4"))
	}

	emit(0, "processing", "Fetching audio from the source")
	audioPath, err := prepareAudio(opts)
	if err != nil {
		return nil, err
	}
	fmt.Printf("✅ Audio saved to: %s\n\n", audioPath)
	emit(0, "completed", "Audio ready")

	emit(1, "processing", "Running Whisper with word-level timestamps")
	fmt.Println("🎙️ Transcribing with Whisper...")
	transcript, err := transcriber.Transcribe(audioPath, opts.WorkDir, opts.TranscribeDevice, opts.TranscribeCompute)
	if err != nil {
		return nil, err
	}
	fmt.Printf("\n✅ Transcription complete! %d segments found\n\n", len(transcript.Segments))
	emit(1, "completed", fmt.Sprintf("%d transcript segments", len(transcript.Segments)))

	emit(2, "processing", "Asking Qwen/Ollama for viral moments")
	fmt.Println("🧠 Analyzing transcript for viral clips...")
	result, err := analyzer.Analyze(transcript)
	if err != nil {
		return nil, err
	}
	if opts.ClipCount > 0 && len(result.Clips) > opts.ClipCount {
		result.Clips = result.Clips[:opts.ClipCount]
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
	emit(2, "completed", fmt.Sprintf("%d highlights selected", len(result.Clips)))

	emit(3, "processing", "Getting the full source video")
	fmt.Println("📥 Downloading full video...")
	videoPath, err := prepareVideo(opts)
	if err != nil {
		return nil, err
	}
	fmt.Printf("✅ Video saved to: %s\n\n", videoPath)
	emit(3, "completed", "Source video ready")

	emit(4, "processing", "Extracting highlight segments")
	fmt.Println("✂️  Cutting clips...")
	clipPaths, err := cutter.CutClips(videoPath, opts.WorkDir, result.Clips)
	if err != nil {
		return nil, err
	}
	emit(4, "completed", fmt.Sprintf("%d clips cut", len(clipPaths)))

	emit(5, "processing", "Tracking faces and reframing to 9:16")
	fmt.Println("\n📱 Reframes to 9:16...")
	reframeOpts := reframer.DefaultOptions()
	reframeOpts.Mode = opts.ReframeMode
	reframeOpts.Width = opts.ReframeWidth
	reframeOpts.Height = opts.ReframeHeight
	reframeOpts.RefocusBand = opts.ReframeSmoothing
	reframeOpts.WorkDir = opts.WorkDir
	for i, clipResult := range clipPaths {
		label := "smart face tracking"
		if opts.ReframeMode == "center" {
			label = "center crop"
		}
		fmt.Printf("  🎥 Clip %d (%s)...\n", i+1, label)

		// Pass transcript words and highlight context to reframer
		clip := analyzer.Clip{}
		if i < len(result.Clips) {
			clip = result.Clips[i]
		}
		words := captioner.ExtractWords(transcript, clip.Start, clip.End)
		words = captioner.RemapWords(words, clipResult.KeptSegments)

		contextData := map[string]any{
			"title": clip.Title,
			"hook":  clip.Hook,
			"why":   clip.Why,
			"start": clip.Start,
			"end":   clip.End,
			"words": words,
		}
		if b, err := json.Marshal(contextData); err == nil {
			ctxPath := filepath.Join(opts.WorkDir, fmt.Sprintf("clip_%d_context.json", i+1))
			_ = os.WriteFile(ctxPath, b, 0644)
			reframeOpts.ContextPath = ctxPath
		}
		reframeOpts.Debug = opts.DebugReframe

		if err := reframer.Reframe(clipResult.Path, reframeOpts); err != nil {
			fmt.Printf("    ⚠️  Reframe failed: %v\n", err)
			continue
		}
		fmt.Printf("    ✅ %dx%d ready\n", opts.ReframeWidth, opts.ReframeHeight)
	}
	emit(5, "completed", "Vertical reframing complete")

	emit(6, "processing", "Burning word-by-word captions")
	fmt.Println("\n💬 Adding captions...")
	clipsDir := filepath.Join(opts.WorkDir, "clips")
	captionsOn := opts.Captions
	for i, clipResult := range clipPaths {
		if i >= len(result.Clips) {
			break
		}
		clip := result.Clips[i]
		if !captionsOn {
			continue
		}
		fmt.Printf("  💬 Captioning clip %d: %s\n", i+1, clip.Title)

		words := captioner.ExtractWords(transcript, clip.Start, clip.End)
		if len(words) == 0 {
			fmt.Printf("    ⚠️  No word timestamps found, skipping captions\n")
			continue
		}

		words = captioner.RemapWords(words, clipResult.KeptSegments)
		fmt.Printf("    📝 %d words synced to edited timeline\n", len(words))

		captionedPath := filepath.Join(clipsDir, fmt.Sprintf("final_%d.mp4", i+1))
		if err := captioner.BurnCaptions(clipResult.Path, words, captionedPath); err != nil {
			fmt.Printf("    ⚠️  Failed to burn captions: %v\n", err)
			continue
		}

		os.Remove(clipResult.Path)
		os.Rename(captionedPath, clipResult.Path)
		fmt.Printf("    ✅ Captions synced!\n")
	}
	emit(6, "completed", "Captions ready")

	fmt.Printf("\n🎉 Done! %d clips ready:\n", len(clipPaths))
	outClips := make([]ResultClip, 0, len(clipPaths))
	accents := []string{
		"from-amber-600/30 to-amber-950/80",
		"from-emerald-600/30 to-emerald-950/80",
		"from-blue-600/30 to-blue-950/80",
	}
	reframeLabel := "Speaker tracking"
	if opts.ReframeMode == "center" {
		reframeLabel = "Center crop"
	}
	for i, clipResult := range clipPaths {
		fmt.Printf("  📎 %s\n", clipResult.Path)
		clipMeta := analyzer.Clip{}
		if i < len(result.Clips) {
			clipMeta = result.Clips[i]
		}
		dur, _ := cutter.VideoDuration(clipResult.Path)
		filename := filepath.Base(clipResult.Path)
		outClips = append(outClips, ResultClip{
			ID:                i + 1,
			ClipNumber:        fmt.Sprintf("%02d", i+1),
			Title:             clipMeta.Title,
			Subtitle:          clipMeta.Why,
			TranscriptSnippet: clipMeta.Hook,
			Duration:          dur,
			DurationFormatted: formatDuration(dur),
			Path:              clipResult.Path,
			Filename:          filename,
			VideoURL:          "/api/media/" + filename,
			CaptionsEnabled:   captionsOn,
			ReframingMode:     reframeLabel,
			AspectRatio:       "9:16",
			Score:             90 - i,
			Tags:              []string{"Highlight", "9:16"},
			AccentColor:       accents[i%len(accents)],
			Start:             clipMeta.Start,
			End:               clipMeta.End,
			Hook:              clipMeta.Hook,
			Why:               clipMeta.Why,
		})
	}

	elapsed := time.Since(start)
	res := &Result{
		Status:         "completed",
		Source:         source,
		SourceType:     sourceType,
		ProcessingTime: formatClock(elapsed),
		ClipsCount:     len(outClips),
		Clips:          outClips,
		Timestamp:      time.Now().Format(time.RFC3339),
	}
	if b, err := json.MarshalIndent(res, "", "  "); err == nil {
		_ = os.WriteFile(filepath.Join(opts.WorkDir, "latest_result.json"), b, 0644)
	}
	return res, nil
}

func prepareAudio(opts Options) (string, error) {
	if opts.LocalVideo != "" {
		audioPath := filepath.Join(opts.WorkDir, "audio.mp3")
		fmt.Println("📥 Extracting audio from uploaded video...")
		cmd := exec.Command("ffmpeg", "-y", "-i", opts.LocalVideo, "-vn", "-acodec", "libmp3lame", "-q:a", "4", audioPath)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			return "", fmt.Errorf("failed to extract audio: %w", err)
		}
		return audioPath, nil
	}
	fmt.Println("📥 Downloading audio...")
	return transcriber.DownloadAudio(opts.URL, opts.WorkDir)
}

func prepareVideo(opts Options) (string, error) {
	if opts.LocalVideo != "" {
		dest := filepath.Join(opts.WorkDir, "video.mp4")
		if absSrc, err := filepath.Abs(opts.LocalVideo); err == nil {
			if absDst, err := filepath.Abs(dest); err == nil && absSrc == absDst {
				return dest, nil
			}
		}
		if err := copyFile(opts.LocalVideo, dest); err != nil {
			return "", err
		}
		return dest, nil
	}
	return cutter.DownloadVideo(opts.URL, opts.WorkDir)
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Close()
}

func formatDuration(sec float64) string {
	if sec < 0 {
		sec = 0
	}
	total := int(sec + 0.5)
	return fmt.Sprintf("%02d:%02d", total/60, total%60)
}

func formatClock(d time.Duration) string {
	total := int(d.Seconds())
	return fmt.Sprintf("%02d:%02d", total/60, total%60)
}

func ParseClipCount(value string) int {
	value = strings.TrimSpace(strings.ToLower(value))
	if value == "" || value == "auto" {
		return 0
	}
	n, err := strconv.Atoi(value)
	if err != nil || n < 0 {
		return 0
	}
	return n
}
