// Package main - GPU miner watchdog daemon
// gpu-watchdog: Health monitoring daemon với auto-restart capability
package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/watchdog"
	"go.uber.org/zap"
)

func main() {
	// Setup logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	// Load config
	cfg := &watchdog.Config{
		BinaryPath:       "/usr/local/bin/gpu-miner",
		Args:             []string{"--config", "/etc/miner/config.yaml"},
		HealthCheckURL:   "http://localhost:8080/health",
		CheckInterval:    10 * time.Second,
		UnhealthyTimeout: 30 * time.Second,
		MaxRestarts:      5,
		RestartBackoff:   5 * time.Second,
		ShutdownTimeout:  30 * time.Second,
	}

	// Create watchdog
	wd := watchdog.New(cfg, logger)

	// Setup context với signal handling
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		logger.Info("Received shutdown signal", zap.String("signal", sig.String()))
		cancel()
	}()

	// Start watchdog
	logger.Info("Starting GPU miner watchdog",
		zap.String("binary", cfg.BinaryPath),
		zap.Duration("check_interval", cfg.CheckInterval),
	)

	if err := wd.Run(ctx); err != nil {
		logger.Fatal("Watchdog error", zap.Error(err))
	}

	logger.Info("Watchdog stopped")
}
