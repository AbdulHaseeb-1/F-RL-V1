// Package store holds shared in-memory state for the pipeline and its results.
package store

import (
	"os"
	"os/exec"
	"sync"
	"time"
)

// Status represents the current pipeline status.
type Status string

const (
	StatusIdle      Status = "idle"
	StatusRunning   Status = "running"
	StatusCompleted Status = "completed"
	StatusFailed    Status = "failed"
)

// Run holds metadata for one pipeline execution.
type Run struct {
	ID        string         `json:"id"`
	Status    Status         `json:"status"`
	Stage     string         `json:"stage"`
	StartedAt time.Time      `json:"started_at"`
	EndedAt   *time.Time     `json:"ended_at,omitempty"`
	RunName   string         `json:"run_name"`
	Config    map[string]any `json:"config,omitempty"`
	Error     string         `json:"error,omitempty"`
}

var (
	mu      sync.RWMutex
	active  *Run
	history []Run
	process *exec.Cmd
)

// GetActive returns a copy of the active run (nil if none).
func GetActive() *Run {
	mu.RLock()
	defer mu.RUnlock()
	if active == nil {
		return nil
	}
	cp := *active
	return &cp
}

// SetActive replaces the active run.
func SetActive(r *Run) {
	mu.Lock()
	defer mu.Unlock()
	active = r
}

// UpdateStage updates the stage field on the active run.
func UpdateStage(stage string) {
	mu.Lock()
	defer mu.Unlock()
	if active != nil {
		active.Stage = stage
	}
}

// FinishActive marks the active run as completed/failed, appends to history.
func FinishActive(status Status, errMsg string) {
	mu.Lock()
	defer mu.Unlock()
	if active == nil {
		return
	}
	now := time.Now().UTC()
	active.Status = status
	active.EndedAt = &now
	active.Error = errMsg
	history = append(history, *active)
	if len(history) > 100 {
		history = history[len(history)-100:]
	}
	active = nil
}

// GetHistory returns a copy of the run history (most recent first).
func GetHistory() []Run {
	mu.RLock()
	defer mu.RUnlock()
	out := make([]Run, len(history))
	copy(out, history)
	// reverse
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	return out
}

// SetProcess stores the running subprocess handle.
func SetProcess(c *exec.Cmd) {
	mu.Lock()
	defer mu.Unlock()
	process = c
}

// GetProcess returns the current subprocess (nil if none).
func GetProcess() *exec.Cmd {
	mu.RLock()
	defer mu.RUnlock()
	return process
}

// StopProcess sends SIGTERM to the running process.
func StopProcess() error {
	mu.Lock()
	defer mu.Unlock()
	if process == nil || process.Process == nil {
		return nil
	}
	err := process.Process.Signal(os.Interrupt)
	process = nil
	return err
}
