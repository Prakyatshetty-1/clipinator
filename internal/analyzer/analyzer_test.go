package analyzer

import (
	"encoding/json"
	"os"
	"testing"

	"github.com/Verifieddanny/clipreator-cli/internal/transcriber"
)

func TestAnalyzeOfflineOllama(t *testing.T) {
	audioJson := "../../.clipreator_tmp/audio.json"
	data, err := os.ReadFile(audioJson)
	if err != nil {
		t.Skip("no cached audio.json found, skipping test")
	}

	var transcript transcriber.Transcript
	if err := json.Unmarshal(data, &transcript); err != nil {
		t.Fatalf("failed to unmarshal audio.json: %v", err)
	}

	// Ensure no cloud keys are set
	os.Unsetenv("ANTHROPIC_API_KEY")
	os.Unsetenv("OPENAI_API_KEY")
	os.Unsetenv("OLLAMA_MODEL")

	// Only test with the first 20 segments so the test completes quickly
	if len(transcript.Segments) > 20 {
		transcript.Segments = transcript.Segments[:20]
	}

	res, err := Analyze(&transcript)
	if err != nil {
		t.Fatalf("Analyze failed with offline Ollama: %v", err)
	}

	if len(res.Clips) == 0 {
		t.Fatalf("Expected at least one clip, got 0")
	}

	t.Logf("Found %d clips with Ollama qwen2.5:latest:", len(res.Clips))
	for i, c := range res.Clips {
		t.Logf("  Clip %d: %s (%.1f -> %.1f)", i+1, c.Title, c.Start, c.End)
	}
}
