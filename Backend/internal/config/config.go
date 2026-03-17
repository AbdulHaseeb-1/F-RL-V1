package config

import "os"

type Config struct {
	Port        string
	Env         string
	AllowOrigin string
	// RunsDir is the path to the Python pipeline's runs/ output directory.
	RunsDir string
	// PythonDir is the working directory for launching the Python pipeline.
	PythonDir string
}

func Load() *Config {
	return &Config{
		Port:        getEnv("PORT", "8080"),
		Env:         getEnv("APP_ENV", "development"),
		AllowOrigin: getEnv("ALLOW_ORIGIN", "http://localhost:5173"),
		RunsDir:     getEnv("RUNS_DIR", "../btc-hybrid-trader/runs"),
		PythonDir:   getEnv("PYTHON_DIR", "../btc-hybrid-trader"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
