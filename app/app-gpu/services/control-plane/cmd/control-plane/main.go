package main

import (
    "context"
    "os"
    "os/signal"
    "syscall"

    "github.com/opus-gpu/app-gpu/control-plane/internal/server"
    "go.uber.org/zap"
)

func main() {
    logger, _ := zap.NewProduction()
    defer logger.Sync() //nolint:errcheck

    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer cancel()

    addr := ":8080"
    if fromEnv := os.Getenv("CONTROL_PLANE_ADDR"); fromEnv != "" {
        addr = fromEnv
    }

    _, err := server.Start(ctx, logger, server.Options{Addr: addr})
    if err != nil {
        logger.Fatal("unable to start control-plane", zap.Error(err))
    }

    <-ctx.Done()
}
