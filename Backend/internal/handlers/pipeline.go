package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/store"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

// pythonDir is set once at startup via InitPipeline.
var pythonDir string

// InitPipeline configures the Python working directory used to launch the pipeline.
func InitPipeline(dir string) {
	pythonDir = dir
}

// PipelineStatus godoc
// GET /api/pipeline/status
func PipelineStatus(w http.ResponseWriter, r *http.Request) {
	run := store.GetActive()
	if run == nil {
		response.JSON(w, http.StatusOK, map[string]any{
			"status": store.StatusIdle,
			"stage":  "",
		})
		return
	}
	response.JSON(w, http.StatusOK, run)
}

// PipelineStart godoc
// POST /api/pipeline/start
func PipelineStart(w http.ResponseWriter, r *http.Request) {
	if store.GetActive() != nil {
		response.Error(w, http.StatusConflict, "pipeline already running")
		return
	}

	var cfg map[string]any
	if r.ContentLength > 0 {
		_ = json.NewDecoder(r.Body).Decode(&cfg)
	}

	runName := fmt.Sprintf("run_%s", time.Now().UTC().Format("20060102_150405"))
	run := &store.Run{
		ID:        runName,
		Status:    store.StatusRunning,
		Stage:     "data_load",
		StartedAt: time.Now().UTC(),
		RunName:   runName,
		Config:    cfg,
	}
	store.SetActive(run)

	// Launch the Python pipeline in a goroutine.
	go launchPipeline(runName, cfg)

	response.JSON(w, http.StatusAccepted, run)
}

// PipelineStop godoc
// POST /api/pipeline/stop
func PipelineStop(w http.ResponseWriter, r *http.Request) {
	if store.GetActive() == nil {
		response.Error(w, http.StatusConflict, "no pipeline running")
		return
	}
	if err := store.StopProcess(); err != nil {
		response.Error(w, http.StatusInternalServerError, "failed to stop pipeline: "+err.Error())
		return
	}
	store.FinishActive(store.StatusFailed, "stopped by user")
	response.OK(w, "pipeline stopped")
}

// PipelineHistory godoc
// GET /api/pipeline/history
func PipelineHistory(w http.ResponseWriter, r *http.Request) {
	response.JSON(w, http.StatusOK, store.GetHistory())
}

// launchPipeline runs the Python orchestrator as a subprocess.
func launchPipeline(runName string, cfg map[string]any) {
	dir := pythonDir
	if dir == "" {
		dir = "../btc-hybrid-trader"
	}

	cmd := exec.Command(resolvePythonExecutable(dir), "-m", "src.pipeline.orchestrator",
		"--run-name", runName)
	cmd.Dir = dir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Start the process first so cmd.Process is populated before storing it.
	if err := cmd.Start(); err != nil {
		store.FinishActive(store.StatusFailed, "failed to start: "+err.Error())
		return
	}
	store.SetProcess(cmd)

	if err := cmd.Wait(); err != nil {
		store.FinishActive(store.StatusFailed, err.Error())
	} else {
		store.FinishActive(store.StatusCompleted, "")
	}
	store.SetProcess(nil)
}

func resolvePythonExecutable(dir string) string {
	candidates := []string{
		filepath.Join(dir, ".venv", "Scripts", "python.exe"),
		filepath.Join(dir, ".venv", "bin", "python"),
	}

	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}

	return "python"
}
