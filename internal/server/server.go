package server

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"

	"github.com/Verifieddanny/clipreator-cli/internal/pipeline"
)

type Server struct {
	Root    string
	WorkDir string
	mu      sync.Mutex
	running bool
}

type generateRequest struct {
	URL              string `json:"url"`
	SmartReframing   *bool  `json:"smartReframing"`
	Captions         *bool  `json:"captions"`
	ReframeMode      string `json:"reframeMode"`
	ClipCount        string `json:"clipCount"`
	ReframeWidth     int    `json:"reframeWidth"`
	ReframeHeight    int    `json:"reframeHeight"`
	TranscribeDevice string `json:"transcribeDevice"`
	TranscribeCompute string `json:"transcribeCompute"`
}

var clipFileRe = regexp.MustCompile(`^clip_\d+\.mp4$`)

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/generate", s.handleGenerate)
	mux.HandleFunc("/api/media/", s.handleMedia)
	mux.HandleFunc("/api/clips", s.handleListClips)

	dist := filepath.Join(s.Root, "frontend", "dist")
	if info, err := os.Stat(dist); err == nil && info.IsDir() {
		fs := http.FileServer(http.Dir(dist))
		mux.Handle("/", fs)
	} else {
		mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/" {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Content-Type", "text/plain; charset=utf-8")
			fmt.Fprintf(w, "Clipreator API is running. Start the frontend with: cd frontend && npm run dev\n")
		})
	}

	return withCORS(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":      true,
		"running": s.isRunning(),
		"workDir": s.WorkDir,
	})
}

func (s *Server) handleListClips(w http.ResponseWriter, r *http.Request) {
	resultPath := filepath.Join(s.WorkDir, "latest_result.json")
	if data, err := os.ReadFile(resultPath); err == nil {
		var res pipeline.Result
		if err := json.Unmarshal(data, &res); err == nil && len(res.Clips) > 0 {
			writeJSON(w, http.StatusOK, res)
			return
		}
	}

	clipsDir := filepath.Join(s.WorkDir, "clips")
	entries, err := os.ReadDir(clipsDir)
	if err != nil {
		writeJSON(w, http.StatusOK, map[string]any{"clips": []any{}})
		return
	}
	var clips []map[string]any
	for _, entry := range entries {
		name := entry.Name()
		if !clipFileRe.MatchString(name) {
			continue
		}
		clips = append(clips, map[string]any{
			"filename": name,
			"videoUrl": "/api/media/" + name,
		})
	}
	if clips == nil {
		clips = []map[string]any{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"clips": clips})
}

func (s *Server) handleMedia(w http.ResponseWriter, r *http.Request) {
	name := filepath.Base(r.URL.Path)
	if !clipFileRe.MatchString(name) {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	path := filepath.Join(s.WorkDir, "clips", name)
	if _, err := os.Stat(path); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "video/mp4")
	http.ServeFile(w, r, path)
}

func (s *Server) handleGenerate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.tryStart() {
		writeJSON(w, http.StatusConflict, map[string]string{
			"error": "A generation job is already running",
		})
		return
	}
	defer s.stop()

	req, localVideo, err := s.parseGenerateRequest(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	flusher.Flush()

	send := func(event string, payload any) {
		data, _ := json.Marshal(payload)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event, data)
		flusher.Flush()
	}

	reframeEnabled := true
	if req.SmartReframing != nil {
		reframeEnabled = *req.SmartReframing
	}
	captions := true
	if req.Captions != nil {
		captions = *req.Captions
	}
	mode := req.ReframeMode
	if mode == "" {
		if reframeEnabled {
			mode = "auto"
		} else {
			mode = "center"
		}
	}

	opts := pipeline.Options{
		URL:               req.URL,
		LocalVideo:        localVideo,
		WorkDir:           s.WorkDir,
		ReframeEnabled:    reframeEnabled,
		ReframeMode:       mode,
		ReframeWidth:      req.ReframeWidth,
		ReframeHeight:     req.ReframeHeight,
		Captions:          captions,
		ClipCount:         pipeline.ParseClipCount(req.ClipCount),
		ForceRefresh:      true,
		TranscribeDevice:  normalizeDevice(req.TranscribeDevice),
		TranscribeCompute: normalizeComputeType(req.TranscribeCompute),
		DebugReframe:      os.Getenv("CLIPREATOR_DEBUG_REFRAME") == "1",
		OnProgress: func(p pipeline.Progress) {
			send("step", p)
		},
	}

	result, err := pipeline.Run(opts)
	if err != nil {
		send("error", map[string]string{"message": err.Error()})
		return
	}
	send("complete", result)
}

func (s *Server) parseGenerateRequest(r *http.Request) (generateRequest, string, error) {
	var req generateRequest
	contentType := r.Header.Get("Content-Type")
	if strings.HasPrefix(contentType, "multipart/form-data") {
		if err := r.ParseMultipartForm(32 << 20); err != nil {
			return req, "", fmt.Errorf("invalid upload: %w", err)
		}
		req.URL = r.FormValue("url")
		req.ReframeMode = r.FormValue("reframeMode")
		req.ClipCount = r.FormValue("clipCount")
		req.TranscribeDevice = r.FormValue("transcribeDevice")
		req.TranscribeCompute = r.FormValue("transcribeCompute")
		if v := r.FormValue("smartReframing"); v != "" {
			b := v == "true" || v == "1"
			req.SmartReframing = &b
		}
		if v := r.FormValue("captions"); v != "" {
			b := v == "true" || v == "1"
			req.Captions = &b
		}
		if v := r.FormValue("reframeWidth"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				req.ReframeWidth = n
			}
		}
		if v := r.FormValue("reframeHeight"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				req.ReframeHeight = n
			}
		}
		file, header, err := r.FormFile("file")
		if err != nil {
			if req.URL == "" {
				return req, "", fmt.Errorf("a YouTube URL or video file is required")
			}
			return req, "", nil
		}
		defer file.Close()
		uploadDir := filepath.Join(s.WorkDir, "uploads")
		if err := os.MkdirAll(uploadDir, 0755); err != nil {
			return req, "", err
		}
		dest := filepath.Join(uploadDir, filepath.Base(header.Filename))
		out, err := os.Create(dest)
		if err != nil {
			return req, "", err
		}
		defer out.Close()
		if _, err := io.Copy(out, file); err != nil {
			return req, "", err
		}
		return req, dest, nil
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		return req, "", fmt.Errorf("invalid JSON body")
	}
	if req.URL == "" {
		return req, "", fmt.Errorf("url is required")
	}
	return req, "", nil
}

func (s *Server) tryStart() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.running {
		return false
	}
	s.running = true
	return true
}

func (s *Server) stop() {
	s.mu.Lock()
	s.running = false
	s.mu.Unlock()
}

func (s *Server) isRunning() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.running
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func normalizeDevice(input string) string {
	lower := strings.ToLower(strings.TrimSpace(input))
	switch {
	case lower == "":
		return ""
	case strings.Contains(lower, "cuda") || strings.Contains(lower, "gpu") || strings.Contains(lower, "mps"):
		return "cuda"
	case strings.Contains(lower, "cpu"):
		return "cpu"
	default:
		return input
	}
}

func normalizeComputeType(input string) string {
	lower := strings.ToLower(strings.TrimSpace(input))
	switch lower {
	case "":
		return ""
	case "float16", "fp16":
		return "float16"
	case "int8", "int8_float16", "int8_float32":
		return lower
	case "float32", "fp32":
		return "float32"
	case "default":
		return "default"
	default:
		return input
	}
}

func FindRepoRoot() string {
	cwd, err := os.Getwd()
	if err != nil {
		return "."
	}
	dir := cwd
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return cwd
		}
		dir = parent
	}
}
