package reframer

import (
	"embed"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/Verifieddanny/clipreator-cli/internal/cutter"
)

//go:embed scripts/*.py
var scriptFS embed.FS

type Options struct {
	Mode           string
	Width          int
	Height         int
	RefocusBand    float64
	HoldSeconds    float64
	SceneThreshold float64
	Headroom       float64
	CPU            bool
	WorkDir        string
	ContextPath    string
	Debug          bool
}

func DefaultOptions() Options {
	return Options{
		Mode:           "auto",
		Width:          1080,
		Height:         1920,
		RefocusBand:    0.03,
		HoldSeconds:    2.0,
		SceneThreshold: 28.0,
		Headroom:       0.42,
		CPU:            os.Getenv("CLIPREATOR_REFRAME_CPU") == "1",
		Debug:          os.Getenv("CLIPREATOR_DEBUG_REFRAME") == "1",
	}
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

func findScriptDir(workDir string) (string, error) {
	candidates := []string{
		filepath.Join("internal", "reframer", "scripts"),
		filepath.Join("..", "internal", "reframer", "scripts"),
		filepath.Join("../..", "internal", "reframer", "scripts"),
	}
	for _, c := range candidates {
		target := filepath.Join(c, "reframe.py")
		if info, err := os.Stat(target); err == nil && !info.IsDir() {
			if abs, err := filepath.Abs(c); err == nil {
				return abs, nil
			}
			return c, nil
		}
	}
	scriptDir := filepath.Join(workDir, "reframe_scripts")
	return extractScripts(scriptDir)
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

func CenterCrop(inputPath, outputPath string, width, height int) error {
	return cutter.CenterCropVertical(inputPath, outputPath, width, height)
}

func Reframe(inputPath string, opts Options) error {
	if opts.Width <= 0 {
		opts.Width = 1080
	}
	if opts.Height <= 0 {
		opts.Height = 1920
	}
	mode := strings.ToLower(strings.TrimSpace(opts.Mode))
	if mode == "" {
		mode = "auto"
	}

	if abs, err := filepath.Abs(inputPath); err == nil {
		inputPath = abs
	}
	tmpOut := inputPath + ".reframe.mp4"
	defer os.Remove(tmpOut)

	if mode == "center" {
		if err := CenterCrop(inputPath, tmpOut, opts.Width, opts.Height); err != nil {
			return err
		}
		return replaceFile(tmpOut, inputPath)
	}

	scriptDir, err := findScriptDir(opts.WorkDir)
	if err != nil {
		fmt.Printf("    ⚠️  Could not locate reframe scripts (%v); using center crop\n", err)
		if err := CenterCrop(inputPath, tmpOut, opts.Width, opts.Height); err != nil {
			return err
		}
		return replaceFile(tmpOut, inputPath)
	}

	modelDir := os.Getenv("CLIPREATOR_MODEL_DIR")
	if modelDir == "" {
		home, _ := os.UserHomeDir()
		modelDir = filepath.Join(home, ".clipreator", "models")
	}

	args := []string{
		filepath.Join(scriptDir, "reframe.py"),
		"--input", inputPath,
		"--output", tmpOut,
		"--width", fmt.Sprintf("%d", opts.Width),
		"--height", fmt.Sprintf("%d", opts.Height),
		"--headroom", fmt.Sprintf("%.3f", opts.Headroom),
		"--hold-seconds", fmt.Sprintf("%.3f", opts.HoldSeconds),
		"--scene-threshold", fmt.Sprintf("%.3f", opts.SceneThreshold),
		"--refocus-band", fmt.Sprintf("%.4f", opts.RefocusBand),
		"--model-dir", modelDir,
	}
	if opts.CPU {
		args = append(args, "--cpu")
	}
	if opts.ContextPath != "" {
		args = append(args, "--context", opts.ContextPath)
	}
	if opts.Debug {
		args = append(args, "--debug")
	}

	cmd := exec.Command(pythonBin(), args...)
	cmd.Dir = scriptDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fmt.Printf("    ⚠️  Smart reframe failed (%v); using center crop\n", err)
		os.Remove(tmpOut)
		if err := CenterCrop(inputPath, tmpOut, opts.Width, opts.Height); err != nil {
			return err
		}
	}

	if _, err := os.Stat(tmpOut); err != nil {
		if err := CenterCrop(inputPath, tmpOut, opts.Width, opts.Height); err != nil {
			return err
		}
	}
	return replaceFile(tmpOut, inputPath)
}

func replaceFile(src, dest string) error {
	if err := os.Rename(src, dest); err == nil {
		return nil
	}
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	if err := os.WriteFile(dest, data, 0644); err != nil {
		return err
	}
	os.Remove(src)
	return nil
}
