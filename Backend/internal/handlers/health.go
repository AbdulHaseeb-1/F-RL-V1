package handlers

import (
	"net/http"
	"runtime"
	"time"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

var startTime = time.Now()

func Health(w http.ResponseWriter, r *http.Request) {
	response.JSON(w, http.StatusOK, map[string]any{
		"status":   "ok",
		"uptime":   time.Since(startTime).String(),
		"go":       runtime.Version(),
		"goroutines": runtime.NumGoroutine(),
	})
}
