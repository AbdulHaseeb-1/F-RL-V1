package router

import (
	"net/http"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/config"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/handlers"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/middleware"
)

func New(cfg *config.Config) http.Handler {
	// Propagate config to handlers that need filesystem paths.
	handlers.InitPipeline(cfg.PythonDir)
	handlers.InitMonitor(cfg.RunsDir)

	mux := http.NewServeMux()

	// Health
	mux.HandleFunc("GET /api/health", handlers.Health)

	// Pipeline
	mux.HandleFunc("GET /api/pipeline/status", handlers.PipelineStatus)
	mux.HandleFunc("POST /api/pipeline/start", handlers.PipelineStart)
	mux.HandleFunc("POST /api/pipeline/stop", handlers.PipelineStop)
	mux.HandleFunc("GET /api/pipeline/history", handlers.PipelineHistory)

	// Monitor
	mux.HandleFunc("GET /api/monitor/progress", handlers.MonitorProgress)
	mux.HandleFunc("GET /api/monitor/metrics/{stage}", handlers.MonitorMetrics)
	mux.HandleFunc("GET /api/monitor/gates", handlers.MonitorGates)

	// Backtest
	mux.HandleFunc("GET /api/backtest/equity", handlers.BacktestEquity)
	mux.HandleFunc("GET /api/backtest/trades", handlers.BacktestTrades)
	mux.HandleFunc("GET /api/backtest/metrics", handlers.BacktestMetrics)
	mux.HandleFunc("GET /api/backtest/risk-events", handlers.BacktestRiskEvents)

	// Signals
	mux.HandleFunc("GET /api/signals/recent", handlers.SignalsRecent)
	mux.HandleFunc("GET /api/signals/stats", handlers.SignalsStats)

	// Chain middleware: recover -> logger -> cors -> mux
	return middleware.Recover(
		middleware.Logger(
			middleware.CORS(cfg.AllowOrigin)(mux),
		),
	)
}
