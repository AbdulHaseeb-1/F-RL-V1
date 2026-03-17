package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/AbdulHaseeb-1/F-RL-V1/backend/pkg/response"
)

// GET /api/v1/items
func ListItems(w http.ResponseWriter, r *http.Request) {
	items := []map[string]any{
		{"id": 1, "name": "Item One"},
		{"id": 2, "name": "Item Two"},
	}
	response.JSON(w, http.StatusOK, items)
}

// POST /api/v1/items
func CreateItem(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	response.JSON(w, http.StatusCreated, body)
}
