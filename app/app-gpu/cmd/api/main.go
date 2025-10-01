package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/opus-gpu/app-gpu/internal/api"
	"github.com/opus-gpu/app-gpu/internal/metrics"
	"github.com/opus-gpu/app-gpu/pkg/protocol"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/sirupsen/logrus"
	"github.com/spf13/viper"
	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"
)

var (
	logger = logrus.New()
)

func main() {
	// Khởi tạo cấu hình
	initConfig()
	
	// Khởi tạo logger
	setupLogger()
	
	logger.Info("🚀 Starting GPU Mining API Gateway...")
	
	// Khởi tạo metrics collector
	metricsCollector := metrics.NewCollector()
	metricsCollector.Register()
	
	// Tạo gRPC server
	grpcServer := grpc.NewServer(
		grpc.UnaryInterceptor(api.LoggingInterceptor(logger)),
		grpc.StreamInterceptor(api.StreamLoggingInterceptor(logger)),
	)
	
	// Đăng ký services
	apiService := api.NewAPIService(logger)
	protocol.RegisterGPUMiningServiceServer(grpcServer, apiService)
	
	// Health check service
	healthServer := health.NewServer()
	grpc_health_v1.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("gpu.mining.api", grpc_health_v1.HealthCheckResponse_SERVING)
	
	// Start gRPC server
	grpcPort := viper.GetString("grpc.port")
	grpcListener, err := net.Listen("tcp", ":"+grpcPort)
	if err != nil {
		logger.Fatalf("Failed to listen on port %s: %v", grpcPort, err)
	}
	
	go func() {
		logger.Infof("✅ gRPC server listening on port %s", grpcPort)
		if err := grpcServer.Serve(grpcListener); err != nil {
			logger.Fatalf("gRPC server failed: %v", err)
		}
	}()
	
	// Start HTTP server cho metrics
	httpPort := viper.GetString("http.port")
	httpMux := http.NewServeMux()
	httpMux.Handle("/metrics", promhttp.Handler())
	httpMux.HandleFunc("/health", healthCheckHandler)
	httpMux.HandleFunc("/ready", readinessHandler)
	
	httpServer := &http.Server{
		Addr:    ":" + httpPort,
		Handler: httpMux,
	}
	
	go func() {
		logger.Infof("✅ HTTP server listening on port %s", httpPort)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("HTTP server failed: %v", err)
		}
	}()
	
	// Graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan
	
	logger.Info("🛑 Shutting down gracefully...")
	
	// Shutdown sequence
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	// Stop accepting new requests
	healthServer.SetServingStatus("gpu.mining.api", grpc_health_v1.HealthCheckResponse_NOT_SERVING)
	
	// Graceful stop gRPC
	grpcServer.GracefulStop()
	
	// Shutdown HTTP server
	if err := httpServer.Shutdown(ctx); err != nil {
		logger.Errorf("HTTP server shutdown error: %v", err)
	}
	
	logger.Info("✅ API Gateway shutdown complete")
}

func initConfig() {
	viper.SetDefault("grpc.port", "50051")
	viper.SetDefault("http.port", "8080")
	viper.SetDefault("log.level", "info")
	viper.SetDefault("log.format", "json")
	
	viper.SetEnvPrefix("GPU_API")
	viper.AutomaticEnv()
	
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath("/etc/gpu-mining/")
	viper.AddConfigPath("./configs/")
	
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			panic(fmt.Errorf("fatal error loading config: %w", err))
		}
	}
}

func setupLogger() {
	level, err := logrus.ParseLevel(viper.GetString("log.level"))
	if err != nil {
		level = logrus.InfoLevel
	}
	logger.SetLevel(level)
	
	if viper.GetString("log.format") == "json" {
		logger.SetFormatter(&logrus.JSONFormatter{
			TimestampFormat: time.RFC3339Nano,
		})
	} else {
		logger.SetFormatter(&logrus.TextFormatter{
			FullTimestamp:   true,
			TimestampFormat: time.RFC3339,
		})
	}
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"healthy"}`))
}

func readinessHandler(w http.ResponseWriter, r *http.Request) {
	// Check dependencies (orchestrator, database, etc.)
	// For now, always return ready
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ready"}`))
}
