package transcriber

import (
	"bytes"
	"embed"
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

//go:embed scripts/*.py
var scriptFS embed.FS

type Word struct {
	Text  string  `json:"word"`
	Start float64 `json:"start"`
	End   float64 `json:"end"`
}

type Segment struct {
	Start float64 `json:"start"`
	End   float64 `json:"end"`
	Text  string  `json:"text"`
	Words []Word  `json:"words"`
}

type Transcript struct {
	Segments []Segment `json:"segments"`
	Text     string    `json:"text"`
}

func DownloadAudio(url, outputDir string) (string, error) {
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return "", err
	}
	outputPath := filepath.Join(outputDir, "audio.mp3")

	cmd := exec.Command("yt-dlp",
		"-x", "--audio-format", "mp3",
		"--no-warnings",
		"-o", outputPath,
		url,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to download audio: %w", err)
	}
	return outputPath, nil
}

func pythonBin() string {
	if p := os.Getenv("CLIPREATOR_PYTHON"); p != "" {
		return p
	}
	if venv := os.Getenv("VIRTUAL_ENV"); venv != "" {
		p := filepath.Join(venv, "bin", "python")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	for _, rel := range []string{".venv/bin/python", "../.venv/bin/python", "../../.venv/bin/python"} {
		if _, err := os.Stat(rel); err == nil {
			if abs, err := filepath.Abs(rel); err == nil {
				return abs
			}
			return rel
		}
	}
	for _, c := range []string{"python3", "python"} {
		if path, err := exec.LookPath(c); err == nil {
			return path
		}
	}
	return "python3"
}

func extractScripts(dest string) (string, error) {
	if err := os.MkdirAll(dest, 0755); err != nil {
		return "", err
	}
	entries, err := fs.ReadDir(scriptFS, "scripts")
	if err != nil {
		return "", err
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		data, err := scriptFS.ReadFile("scripts/" + entry.Name())
		if err != nil {
			return "", err
		}
		if err := os.WriteFile(filepath.Join(dest, entry.Name()), data, 0644); err != nil {
			return "", err
		}
	}
	return dest, nil
}

func findScript(workDir string) (string, error) {
	// 1. Direct on-disk scripts inside repository
	candidates := []string{
		filepath.Join("internal", "transcriber", "scripts", "transcribe.py"),
		filepath.Join("..", "internal", "transcriber", "scripts", "transcribe.py"),
		filepath.Join(workDir, "transcriber_scripts", "transcribe.py"),
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			return filepath.Abs(c)
		}
	}

	// 2. Extract embedded script into workDir/transcriber_scripts
	scriptDir := filepath.Join(workDir, "transcriber_scripts")
	if _, err := extractScripts(scriptDir); err == nil {
		p := filepath.Join(scriptDir, "transcribe.py")
		if _, err := os.Stat(p); err == nil {
			return filepath.Abs(p)
		}
	}

	return "", fmt.Errorf("transcribe.py not found on disk or embedded")
}

// Transcribe transcribes an audio file using faster-whisper Medium with GPU (CUDA).
// It accepts optional device and computeType overrides.
func Transcribe(audioPath, outputDir string, opts ...string) (*Transcript, error) {
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, err
	}

	model := os.Getenv("WHISPER_MODEL")
	if model == "" {
		model = "medium"
	}

	device := "cuda"
	if len(opts) > 0 && opts[0] != "" {
		device = opts[0]
	} else if env := os.Getenv("WHISPER_DEVICE"); env != "" {
		device = env
	}

	computeType := "float16"
	if len(opts) > 1 && opts[1] != "" {
		computeType = opts[1]
	} else if env := os.Getenv("WHISPER_COMPUTE_TYPE"); env != "" {
		computeType = env
	}

	scriptPath, err := findScript(outputDir)
	if err != nil {
		return nil, fmt.Errorf("faster-whisper script error: %w", err)
	}

	// Free GPU VRAM from Ollama before loading Whisper
	unloadOllamaVRAM()

	// If audio.json already exists and is non-empty, use it unless forced
	jsonPath := filepath.Join(outputDir, "audio.json")
	if os.Getenv("FORCE_TRANSCRIBE") != "1" {
		if fi, err := os.Stat(jsonPath); err == nil && fi.Size() > 100 {
			if data, err := os.ReadFile(jsonPath); err == nil {
				var existing Transcript
				if err := json.Unmarshal(data, &existing); err == nil && len(existing.Segments) > 0 {
					return &existing, nil
				}
			}
		}
	}

	py := pythonBin()

	args := []string{
		scriptPath,
		"--audio", audioPath,
		"--output-dir", outputDir,
		"--model", model,
		"--device", device,
		"--compute-type", computeType,
	}

	cmd := exec.Command(py, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Forward CUDA library paths if needed
	if cudaPath := os.Getenv("CUDA_HOME"); cudaPath != "" {
		cmd.Env = append(os.Environ(), "CUDA_HOME="+cudaPath)
	}

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("faster-whisper transcription failed: %w", err)
	}

	data, err := os.ReadFile(jsonPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read transcript: %w", err)
	}

	var transcript Transcript
	if err := json.Unmarshal(data, &transcript); err != nil {
		return nil, fmt.Errorf("failed to parse transcript: %w", err)
	}

	return &transcript, nil
}

func unloadOllamaVRAM() {
	ollamaURL := os.Getenv("OLLAMA_HOST")
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}
	model := os.Getenv("OLLAMA_MODEL")
	if model == "" {
		model = "qwen2.5:latest"
	}
	payload := []byte(fmt.Sprintf(`{"model":"%s","keep_alive":0}`, model))
	client := http.Client{Timeout: 2 * time.Second}
	req, err := http.NewRequest("POST", ollamaURL+"/api/generate", bytes.NewBuffer(payload))
	if err == nil {
		req.Header.Set("Content-Type", "application/json")
		resp, err := client.Do(req)
		if err == nil {
			resp.Body.Close()
		}
	}
}
