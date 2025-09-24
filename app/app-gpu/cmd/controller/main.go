package main

import (
    "context"
    "fmt"
    "net/http"
    "os"
    "time"

    backoff "github.com/cenkalti/backoff/v4"
    "github.com/sirupsen/logrus"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func main() {
    logger := logrus.New()
    logger.SetFormatter(&logrus.TextFormatter{FullTimestamp: true})

    ctx := context.Background()
    shutdown, err := setupTracer(ctx)
    if err != nil {
        logger.WithError(err).Fatal("init tracer")
    }
    defer shutdown()

    coreEndpoint := getenv("CORE_ENDPOINT", "http://localhost:8080")
    client := &http.Client{Timeout: 5 * time.Second}

    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ticker.C:
            err := backoff.Retry(func() error {
                req, err := http.NewRequestWithContext(ctx, http.MethodGet, coreEndpoint+"/healthz", nil)
                if err != nil {
                    return err
                }
                res, err := client.Do(req)
                if err != nil {
                    return err
                }
                res.Body.Close()
                if res.StatusCode >= http.StatusMultipleChoices {
                    return fmt.Errorf("core unhealthy: %s", res.Status)
                }
                logger.WithField("endpoint", coreEndpoint).Info("core alive")
                return nil
            }, backoff.NewExponentialBackOff())
            if err != nil {
                logger.WithError(err).Error("health probe failed")
            }
        }
    }
}

func setupTracer(ctx context.Context) (func(), error) {
    endpoint := getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    exporter, err := otlptracehttp.New(ctx, otlptracehttp.WithEndpoint(endpoint), otlptracehttp.WithInsecure())
    if err != nil {
        return nil, err
    }

    provider := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exporter))
    otel.SetTracerProvider(provider)

    return func() {
        ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
        defer cancel()
        _ = provider.Shutdown(ctx)
    }, nil
}

func getenv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
