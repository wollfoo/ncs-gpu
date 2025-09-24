package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "os"
    "time"

    backoff "github.com/cenkalti/backoff/v4"
)

func main() {
    logger := log.New(os.Stdout, "controller ", log.LstdFlags|log.Lmicroseconds)

    ctx := context.Background()
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
                logger.Printf("core alive endpoint=%s", coreEndpoint)
                return nil
            }, backoff.NewExponentialBackOff())
            if err != nil {
                logger.Printf("health probe failed: %v", err)
            }
        }
    }
}

func getenv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
