package reframer

import (
	"os"
	"testing"
)

func TestReframeCenterMode(t *testing.T) {
	input := "../../.clipreator_tmp/test_suite/face_motion.mp4"
	if _, err := os.Stat(input); os.IsNotExist(err) {
		t.Skip("test video not found, skipping")
	}

	tmpCopy := "../../.clipreator_tmp/test_suite/go_test_copy.mp4"
	data, err := os.ReadFile(input)
	if err != nil {
		t.Fatalf("failed to read test video: %v", err)
	}
	if err := os.WriteFile(tmpCopy, data, 0644); err != nil {
		t.Fatalf("failed to write test copy: %v", err)
	}
	defer os.Remove(tmpCopy)

	opts := DefaultOptions()
	opts.Mode = "center"
	opts.Width = 1080
	opts.Height = 1920
	opts.WorkDir = "../../.clipreator_tmp"

	if err := Reframe(tmpCopy, opts); err != nil {
		t.Fatalf("Reframe center mode failed: %v", err)
	}
}

func TestReframeAutoMode(t *testing.T) {
	input := "../../.clipreator_tmp/test_suite/face_motion.mp4"
	if _, err := os.Stat(input); os.IsNotExist(err) {
		t.Skip("test video not found, skipping")
	}

	tmpCopy := "../../.clipreator_tmp/test_suite/go_test_auto_copy.mp4"
	data, err := os.ReadFile(input)
	if err != nil {
		t.Fatalf("failed to read test video: %v", err)
	}
	if err := os.WriteFile(tmpCopy, data, 0644); err != nil {
		t.Fatalf("failed to write test copy: %v", err)
	}
	defer os.Remove(tmpCopy)

	opts := DefaultOptions()
	opts.Mode = "auto"
	opts.Width = 1080
	opts.Height = 1920
	opts.WorkDir = "../../.clipreator_tmp"

	if err := Reframe(tmpCopy, opts); err != nil {
		t.Fatalf("Reframe auto mode failed: %v", err)
	}
}
