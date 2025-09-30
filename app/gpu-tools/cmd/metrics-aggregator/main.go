// Package main - Metrics aggregator service
// metrics-aggregator: Thu thập và tổng hợp metrics từ GPU miner
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/opus-gpu/gpu-tools/internal/aggregator"
	"github.com/opus-gpu/gpu-tools/internal/config"
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

	// Load configuration
	cfg, err := config.LoadAggregatorConfig("")
	if err != nil {
		logger.Fatal("Failed to load config", zap.Error(err))
	}

	// Create metrics aggregator
	agg, err := aggregator.New(cfg, logger)
	if err != nil {
		logger.Fatal("Failed to create aggregator", zap.Error(err))
	}

	// Setup context với signal handling
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		logger.Info("Received shutdown signal")
		cancel()
	}()

	// Start aggregator
	logger.Info("Starting metrics aggregator",
		zap.String("miner_url", cfg.MinerURL),
		zap.Duration("interval", cfg.CollectInterval),
	)

	if err := agg.Run(ctx); err != nil {
		logger.Fatal("Aggregator error", zap.Error(err))
	}

	logger.Info("Metrics aggregator stopped")
}
