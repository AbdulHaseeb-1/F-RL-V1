package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"strconv"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/store"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

// SignalsRecent godoc
// GET /api/signals/recent?n=50
func SignalsRecent(w http.ResponseWriter, r *http.Request) {
	n := 50
	if v := r.URL.Query().Get("n"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			n = parsed
		}
	}

	signals, err := readSignals()
	if err != nil || len(signals) == 0 {
		response.JSON(w, http.StatusOK, []any{})
		return
	}

	if n < len(signals) {
		signals = signals[len(signals)-n:]
	}
	response.JSON(w, http.StatusOK, signals)
}

// SignalsStats godoc
// GET /api/signals/stats
func SignalsStats(w http.ResponseWriter, r *http.Request) {
	signals, err := readSignals()
	if err != nil {
		response.JSON(w, http.StatusOK, map[string]any{
			"total":  0,
			"long":   0,
			"short":  0,
			"skip":   0,
		})
		return
	}

	var long, short, skip int
	for _, s := range signals {
		m, ok := s.(map[string]any)
		if !ok {
			continue
		}
		switch m["signal"] {
		case float64(1), "long", "Long", 1:
			long++
		case float64(-1), "short", "Short", -1:
			short++
		default:
			skip++
		}
	}

	response.JSON(w, http.StatusOK, map[string]any{
		"total": len(signals),
		"long":  long,
		"short": short,
		"skip":  skip,
	})
}

// readSignals reads XGBoost OOS predictions from the current run directory.
func readSignals() ([]any, error) {
	dir := runsDir
	if dir == "" {
		dir = "../btc-hybrid-trader/runs"
	}

	runName := ""
	if run := store.GetActive(); run != nil && run.RunName != "" {
		runName = run.RunName
	} else {
		runName = latestRunDir(dir)
	}
	if runName == "" {
		return nil, os.ErrNotExist
	}

	// Try signals.json, then oos_predictions.json.
	for _, name := range []string{"signals.json", "oos_predictions.json"} {
		path := filepath.Join(dir, runName, name)
		data, err := readJSONFile(path)
		if err == nil {
			if arr, ok := data["signals"].([]any); ok {
				return arr, nil
			}
		}
	}
	return nil, os.ErrNotExist
}
