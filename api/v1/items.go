package handler

import (
	"encoding/json"
	"net/http"
)

func Handler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	switch r.Method {
	case http.MethodGet:
		items := []map[string]any{
			{"id": 1, "name": "Item One"},
			{"id": 2, "name": "Item Two"},
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": items})

	case http.MethodPost:
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "invalid JSON"})
			return
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": body})

	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}
