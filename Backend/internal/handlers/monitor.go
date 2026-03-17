package handlers

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"sort"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/store"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

// runsDir is set once at startup via InitMonitor.
var runsDir string

// InitMonitor configures the runs output directory.
func InitMonitor(dir string) {
	runsDir = dir
}

// MonitorProgress godoc
// GET /api/monitor/progress
func MonitorProgress(w http.ResponseWriter, r *http.Request) {
	data, err := readTrainingHistory()
	if err != nil {
		// Return empty progress when no run data exists yet.
		runName := ""
		if run := store.GetActive(); run != nil {
			runName = run.RunName
		}
		response.JSON(w, http.StatusOK, map[string]any{
			"run_name":           runName,
			"current_stage":      stageFromActive(),
			"stages":             map[string]any{},
			"total_entries":      0,
			"total_duration_sec": 0,
		})
		return
	}

	progress, _ := data["progress"].(map[string]any)
	if progress == nil {
		progress = map[string]any{}
	}
	// Override current_stage from live state when pipeline is running.
	if s := stageFromActive(); s != "" {
		progress["current_stage"] = s
	}
	response.JSON(w, http.StatusOK, progress)
}

// MonitorMetrics godoc
// GET /api/monitor/metrics/{stage}
func MonitorMetrics(w http.ResponseWriter, r *http.Request) {
	stage := r.PathValue("stage")

	data, err := readTrainingHistory()
	if err != nil {
		response.JSON(w, http.StatusOK, []any{})
		return
	}

	rawHistory, _ := data["history"].([]any)
	if rawHistory == nil {
		response.JSON(w, http.StatusOK, []any{})
		return
	}

	if stage == "all" || stage == "" {
		response.JSON(w, http.StatusOK, rawHistory)
		return
	}

	var filtered []any
	for _, entry := range rawHistory {
		m, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		if m["stage"] == stage {
			filtered = append(filtered, m)
		}
	}
	if filtered == nil {
		filtered = []any{}
	}
	response.JSON(w, http.StatusOK, filtered)
}

// gateStages are the pipeline stages whose results represent quality gates.
var gateStages = map[string]bool{
	"xgb_evaluate": true,
	"backtest":      true,
}

// MonitorGates godoc
// GET /api/monitor/gates
func MonitorGates(w http.ResponseWriter, r *http.Request) {
	data, err := readTrainingHistory()
	if err != nil {
		response.JSON(w, http.StatusOK, []map[string]any{})
		return
	}

	rawHistory, _ := data["history"].([]any)
	var gates []map[string]any
	for _, entry := range rawHistory {
		m, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		stageName, _ := m["stage"].(string)
		if !gateStages[stageName] {
			continue
		}
		status, _ := m["status"].(string)
		metrics, _ := m["metrics"].(map[string]any)
		gates = append(gates, map[string]any{
			"stage":     stageName,
			"fold":      m["fold"],
			"status":    status,
			"passed":    status == "passed",
			"metrics":   metrics,
			"timestamp": m["timestamp"],
		})
	}
	if gates == nil {
		gates = []map[string]any{}
	}
	response.JSON(w, http.StatusOK, gates)
}

// readTrainingHistory reads the training_history.json from the most recent run.
func readTrainingHistory() (map[string]any, error) {
	dir := runsDir
	if dir == "" {
		dir = "../btc-hybrid-trader/runs"
	}

	// If a pipeline is active, prefer its run directory.
	if run := store.GetActive(); run != nil && run.RunName != "" {
		path := filepath.Join(dir, run.RunName, "training_history.json")
		return readJSONFile(path)
	}

	// Otherwise find the most recently modified run directory.
	entries, err := os.ReadDir(dir)
	if err != nil || len(entries) == 0 {
		return nil, os.ErrNotExist
	}

	// Sort by name descending (run_YYYYMMDD_HHMMSS format sorts chronologically).
	dirs := make([]os.DirEntry, 0, len(entries))
	for _, e := range entries {
		if e.IsDir() {
			dirs = append(dirs, e)
		}
	}
	if len(dirs) == 0 {
		return nil, os.ErrNotExist
	}
	sort.Slice(dirs, func(i, j int) bool {
		return dirs[i].Name() > dirs[j].Name()
	})

	path := filepath.Join(dir, dirs[0].Name(), "training_history.json")
	return readJSONFile(path)
}

func readJSONFile(path string) (map[string]any, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var data map[string]any
	if err := json.NewDecoder(f).Decode(&data); err != nil {
		return nil, err
	}
	return data, nil
}

func stageFromActive() string {
	if run := store.GetActive(); run != nil {
		return run.Stage
	}
	return ""
}
