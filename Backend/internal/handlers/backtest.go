package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"sort"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/store"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

// BacktestEquity godoc
// GET /api/backtest/equity
func BacktestEquity(w http.ResponseWriter, r *http.Request) {
	data, err := readBacktestResults()
	if err != nil {
		response.JSON(w, http.StatusOK, []any{})
		return
	}
	equity, _ := data["equity_curve"].([]any)
	if equity == nil {
		equity = []any{}
	}
	response.JSON(w, http.StatusOK, equity)
}

// BacktestTrades godoc
// GET /api/backtest/trades
func BacktestTrades(w http.ResponseWriter, r *http.Request) {
	data, err := readBacktestResults()
	if err != nil {
		response.JSON(w, http.StatusOK, []any{})
		return
	}
	trades, _ := data["trades"].([]any)
	if trades == nil {
		trades = []any{}
	}
	response.JSON(w, http.StatusOK, trades)
}

// BacktestMetrics godoc
// GET /api/backtest/metrics
func BacktestMetrics(w http.ResponseWriter, r *http.Request) {
	data, err := readBacktestResults()
	if err != nil {
		response.JSON(w, http.StatusOK, map[string]any{})
		return
	}
	metrics, _ := data["metrics"].(map[string]any)
	if metrics == nil {
		metrics = map[string]any{}
	}
	response.JSON(w, http.StatusOK, metrics)
}

// BacktestRiskEvents godoc
// GET /api/backtest/risk-events
func BacktestRiskEvents(w http.ResponseWriter, r *http.Request) {
	data, err := readBacktestResults()
	if err != nil {
		response.JSON(w, http.StatusOK, []any{})
		return
	}
	events, _ := data["risk_events"].([]any)
	if events == nil {
		events = []any{}
	}
	response.JSON(w, http.StatusOK, events)
}

// readBacktestResults looks for backtest_results.json in the current (or latest) run directory.
func readBacktestResults() (map[string]any, error) {
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

	// Try backtest_results.json first, then run_summary.json as fallback.
	for _, name := range []string{"backtest_results.json", "run_summary.json"} {
		path := filepath.Join(dir, runName, name)
		data, err := readJSONFile(path)
		if err == nil {
			return data, nil
		}
	}
	return nil, os.ErrNotExist
}

// latestRunDir returns the name of the most recently created run subdirectory.
func latestRunDir(dir string) string {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return ""
	}
	var dirs []os.DirEntry
	for _, e := range entries {
		if e.IsDir() {
			dirs = append(dirs, e)
		}
	}
	if len(dirs) == 0 {
		return ""
	}
	sort.Slice(dirs, func(i, j int) bool {
		return dirs[i].Name() > dirs[j].Name()
	})
	return dirs[0].Name()
}

// readJSONFile and runsDir are defined in monitor.go (same package).
