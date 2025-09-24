package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type sloPayload struct {
	Service string  `json:"service"`
	Target  float64 `json:"target"`
	Metric  string  `json:"metric"`
}

var (
	requestsTotal = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "control_plane_requests_total",
		Help: "Số lượng request vào control-plane",
	})
	requestLatency = prometheus.NewHistogram(prometheus.HistogramOpts{
		Name:    "control_plane_latency_ms",
		Help:    "Phân phối latency của request",
		Buckets: prometheus.LinearBuckets(5, 10, 10),
	})
)

func main() {
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8080"
	}

	prometheus.MustRegister(requestsTotal, requestLatency)

	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(60 * time.Second))
	r.Post("/slo", handleSLO)
	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	r.Mount("/metrics", promhttp.Handler())

	log.Printf("Control-plane listening on :%s", port)
	if err := http.ListenAndServe(":"+port, r); err != nil {
		log.Fatalf("failed to start control-plane: %v", err)
	}
}

func handleSLO(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	defer func() {
		requestsTotal.Inc()
		requestLatency.Observe(float64(time.Since(start).Milliseconds()))
	}()

	var payload sloPayload
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	log.Printf("Registered SLO: service=%s target=%f metric=%s", payload.Service, payload.Target, payload.Metric)
	w.WriteHeader(http.StatusAccepted)
	_, _ = w.Write([]byte("accepted"))
}

