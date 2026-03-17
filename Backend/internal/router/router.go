package router

import (
	"net/http"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/config"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/handlers"
	"github.com/AbdulHaseeb-1/F-RL-V1/backend/internal/middleware"
)

func New(cfg *config.Config) http.Handler {
	mux := http.NewServeMux()

	// Health
	mux.HandleFunc("GET /health", handlers.Health)

	// API v1
	mux.HandleFunc("GET /api/v1/items", handlers.ListItems)
	mux.HandleFunc("POST /api/v1/items", handlers.CreateItem)

	// Chain middleware: recover -> logger -> cors -> mux
	return middleware.Recover(
		middleware.Logger(
			middleware.CORS(cfg.AllowOrigin)(mux),
		),
	)
}
