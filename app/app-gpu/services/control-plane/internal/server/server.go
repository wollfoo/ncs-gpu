package server

import (
    "context"
    "net/http"

    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
    "go.uber.org/zap"
)

// Options gom hàm Start để tiện mở rộng.
type Options struct {
    Addr string
}

// Start khởi động HTTP control-plane tối thiểu với health endpoint.
func Start(ctx context.Context, logger *zap.Logger, opts Options) (*http.Server, error) {
    r := chi.NewRouter()
    r.Use(middleware.RequestID)
    r.Use(middleware.RealIP)
    r.Use(middleware.Recoverer)

    r.Get("/healthz", func(w http.ResponseWriter, _ *http.Request) {
        w.WriteHeader(http.StatusOK)
        _, _ = w.Write([]byte("ok"))
    })

    srv := &http.Server{
        Addr:    opts.Addr,
        Handler: r,
    }

    go func() {
        <-ctx.Done()
        _ = srv.Shutdown(context.Background())
    }()

    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            logger.Error("control-plane server stopped unexpectedly", zap.Error(err))
        }
    }()

    return srv, nil
}
