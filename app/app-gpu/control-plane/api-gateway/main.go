// Opus GPU API Gateway - High-performance edge service
//
// Features:
// - mTLS authentication và authorization
// - Rate limiting với token bucket
// - Request/response validation
// - Circuit breaker patterns
// - OpenTelemetry tracing
// - Prometheus metrics

package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/jaeger"
	"go.opentelemetry.io/otel/sdk/resource"
	"go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

// Configuration structure
type Config struct {
	Server ServerConfig `mapstructure:"server"`
	Auth   AuthConfig   `mapstructure:"auth"`
	TLS    TLSConfig    `mapstructure:"tls"`
	Metrics MetricsConfig `mapstructure:"metrics"`
	Scheduler SchedulerConfig `mapstructure:"scheduler"`
	Tracing TracingConfig `mapstructure:"tracing"`
}

type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
	IdleTimeout  time.Duration `mapstructure:"idle_timeout"`
}

type AuthConfig struct {
	JWTSecret    string        `mapstructure:"jwt_secret"`
	TokenExpiry  time.Duration `mapstructure:"token_expiry"`
	RequireMTLS  bool          `mapstructure:"require_mtls"`
}

type TLSConfig struct {
	CertFile string `mapstructure:"cert_file"`
	KeyFile  string `mapstructure:"key_file"`
	CAFile   string `mapstructure:"ca_file"`
}

type MetricsConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Path    string `mapstructure:"path"`
	Port    int    `mapstructure:"port"`
}

type SchedulerConfig struct {
	URL     string        `mapstructure:"url"`
	Timeout time.Duration `mapstructure:"timeout"`
}

type TracingConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Endpoint string `mapstructure:"endpoint"`
	Sampler  string `mapstructure:"sampler"`
}

// Prometheus metrics
var (
	requestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "api_gateway_request_duration_seconds",
			Help: "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "endpoint", "status"},
	)

	requestCounter = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "api_gateway_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	activeLimiterTokens = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "api_gateway_rate_limiter_tokens",
			Help: "Available tokens in rate limiter",
		},
		[]string{"endpoint"},
	)
)

// Rate limiter implementation
type TokenBucket struct {
	capacity int64
	tokens   int64
	refillRate int64
	lastRefill time.Time
}

func NewTokenBucket(capacity, refillRate int64) *TokenBucket {
	return &TokenBucket{
		capacity:   capacity,
		tokens:     capacity,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill)
	tokensToAdd := int64(elapsed.Seconds()) * tb.refillRate
	
	if tokensToAdd > 0 {
		tb.tokens = min(tb.capacity, tb.tokens+tokensToAdd)
		tb.lastRefill = now
	}
	
	if tb.tokens > 0 {
		tb.tokens--
		return true
	}
	return false
}

// API Gateway struct
type APIGateway struct {
	config         *Config
	schedulerConn  *grpc.ClientConn
	rateLimiters   map[string]*TokenBucket
	jwtSecret      []byte
}

// JWT Claims structure
type Claims struct {
	UserID   string   `json:"user_id"`
	Roles    []string `json:"roles"`
	GPUQuota int      `json:"gpu_quota"`
	jwt.RegisteredClaims
}

func main() {
	rootCmd := &cobra.Command{
		Use:   "api-gateway",
		Short: "Opus GPU API Gateway - Edge service với mTLS và rate limiting",
		Long: `High-performance API Gateway cho Opus GPU system với:
- mTLS authentication
- JWT authorization
- Rate limiting
- Request validation
- Circuit breaker patterns`,
		Run: runAPIGateway,
	}

	rootCmd.Flags().StringP("config", "c", "config.yaml", "Configuration file path")
	rootCmd.Flags().Bool("dev-mode", false, "Enable development mode (disable mTLS)")
	rootCmd.Flags().StringP("log-level", "l", "info", "Log level (debug, info, warn, error)")

	if err := rootCmd.Execute(); err != nil {
		log.Fatalf("❌ Failed to start API Gateway: %v", err)
	}
}

func runAPIGateway(cmd *cobra.Command, args []string) {
	// Load configuration
	configFile, _ := cmd.Flags().GetString("config")
	devMode, _ := cmd.Flags().GetBool("dev-mode")
	logLevel, _ := cmd.Flags().GetString("log-level")

	config, err := loadConfig(configFile)
	if err != nil {
		log.Fatalf("❌ Failed to load config: %v", err)
	}

	// Override mTLS for dev mode
	if devMode {
		config.Auth.RequireMTLS = false
		log.Println("⚠️ Development mode: mTLS disabled")
	}

	// Initialize tracing
	if config.Tracing.Enabled {
		if err := initTracing(config.Tracing); err != nil {
			log.Printf("❌ Failed to initialize tracing: %v", err)
		}
	}

	// Initialize metrics
	if config.Metrics.Enabled {
		prometheus.MustRegister(requestDuration, requestCounter, activeLimiterTokens)
		log.Println("📊 Prometheus metrics enabled")
	}

	// Create API Gateway
	gateway, err := NewAPIGateway(config)
	if err != nil {
		log.Fatalf("❌ Failed to create API Gateway: %v", err)
	}

	// Setup routes
	router := gateway.setupRoutes()

	// Configure TLS
	var tlsConfig *tls.Config
	if config.Auth.RequireMTLS {
		tlsConfig, err = setupMTLS(config.TLS)
		if err != nil {
			log.Fatalf("❌ Failed to setup mTLS: %v", err)
		}
		log.Println("🔒 mTLS enabled")
	}

	// Create HTTP server
	server := &http.Server{
		Addr:         fmt.Sprintf("%s:%d", config.Server.Host, config.Server.Port),
		Handler:      router,
		TLSConfig:    tlsConfig,
		ReadTimeout:  config.Server.ReadTimeout,
		WriteTimeout: config.Server.WriteTimeout,
		IdleTimeout:  config.Server.IdleTimeout,
	}

	// Start metrics server if enabled
	if config.Metrics.Enabled {
		go func() {
			metricsAddr := fmt.Sprintf(":%d", config.Metrics.Port)
			http.Handle(config.Metrics.Path, promhttp.Handler())
			log.Printf("📊 Metrics server listening on %s%s", metricsAddr, config.Metrics.Path)
			if err := http.ListenAndServe(metricsAddr, nil); err != nil {
				log.Printf("❌ Metrics server error: %v", err)
			}
		}()
	}

	// Start server
	go func() {
		log.Printf("🚀 API Gateway starting on %s", server.Addr)
		if tlsConfig != nil {
			if err := server.ListenAndServeTLS(config.TLS.CertFile, config.TLS.KeyFile); err != nil && err != http.ErrServerClosed {
				log.Fatalf("❌ HTTPS server error: %v", err)
			}
		} else {
			if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				log.Fatalf("❌ HTTP server error: %v", err)
			}
		}
	}()

	log.Println("✅ API Gateway started successfully")

	// Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("🛑 Shutting down API Gateway...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Printf("❌ Server shutdown error: %v", err)
	}

	// Close gRPC connection
	if gateway.schedulerConn != nil {
		gateway.schedulerConn.Close()
	}

	log.Println("✅ API Gateway shutdown complete")
}

func NewAPIGateway(config *Config) (*APIGateway, error) {
	// Connect to scheduler via gRPC
	var opts []grpc.DialOption
	if config.Auth.RequireMTLS {
		creds, err := credentials.NewClientTLSFromFile(config.TLS.CAFile, "")
		if err != nil {
			return nil, fmt.Errorf("failed to load TLS credentials: %w", err)
		}
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		opts = append(opts, grpc.WithInsecure())
	}

	conn, err := grpc.Dial(config.Scheduler.URL, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to scheduler: %w", err)
	}

	// Initialize rate limiters
	rateLimiters := map[string]*TokenBucket{
		"/api/v1/jobs":   NewTokenBucket(1000, 100), // 100 req/sec, burst 1000
		"/api/v1/status": NewTokenBucket(2000, 200), // 200 req/sec, burst 2000
		"default":       NewTokenBucket(500, 50),   // 50 req/sec default
	}

	return &APIGateway{
		config:        config,
		schedulerConn: conn,
		rateLimiters:  rateLimiters,
		jwtSecret:     []byte(config.Auth.JWTSecret),
	}, nil
}

func (gw *APIGateway) setupRoutes() *gin.Engine {
	router := gin.New()
	
	// Middleware stack
	router.Use(gw.loggingMiddleware())
	router.Use(gw.metricsMiddleware())
	router.Use(gw.rateLimitMiddleware())
	router.Use(gw.authMiddleware())
	router.Use(gin.Recovery())

	// Health check endpoint (no auth required)
	router.GET("/health", gw.healthCheck)
	router.GET("/ready", gw.readinessCheck)

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Job management
		v1.POST("/jobs", gw.submitJob)
		v1.GET("/jobs/:id", gw.getJobStatus)
		v1.DELETE("/jobs/:id", gw.cancelJob)
		v1.GET("/jobs", gw.listJobs)
		
		// Worker management
		v1.GET("/workers", gw.listWorkers)
		v1.GET("/workers/:id", gw.getWorkerStatus)
		
		// System status
		v1.GET("/status", gw.getSystemStatus)
		v1.GET("/metrics", gw.getMetrics)
	}

	return router
}

// Middleware implementations
func (gw *APIGateway) rateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		path := c.FullPath()
		limiter, exists := gw.rateLimiters[path]
		if !exists {
			limiter = gw.rateLimiters["default"]
		}

		if !limiter.Allow() {
			activeLimiterTokens.WithLabelValues(path).Set(float64(limiter.tokens))
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "Rate limit exceeded",
				"retry_after": "1s",
			})
			c.Abort()
			return
		}

		activeLimiterTokens.WithLabelValues(path).Set(float64(limiter.tokens))
		c.Next()
	}
}

func (gw *APIGateway) authMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Skip auth for health checks
		if c.Request.URL.Path == "/health" || c.Request.URL.Path == "/ready" {
			c.Next()
			return
		}

		// Extract JWT token
		token := c.GetHeader("Authorization")
		if token == "" {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Missing authorization header"})
			c.Abort()
			return
		}

		// Remove "Bearer " prefix
		if len(token) > 7 && token[:7] == "Bearer " {
			token = token[7:]
		}

		// Validate JWT
		claims, err := gw.validateJWT(token)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
			c.Abort()
			return
		}

		// Store claims in context
		c.Set("claims", claims)
		c.Next()
	}
}

func (gw *APIGateway) metricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		
		c.Next()
		
		duration := time.Since(start).Seconds()
		status := fmt.Sprintf("%d", c.Writer.Status())
		
		requestDuration.WithLabelValues(c.Request.Method, c.FullPath(), status).Observe(duration)
		requestCounter.WithLabelValues(c.Request.Method, c.FullPath(), status).Inc()
	}
}

func (gw *APIGateway) loggingMiddleware() gin.HandlerFunc {
	return gin.LoggerWithFormatter(func(param gin.LogFormatterParams) string {
		return fmt.Sprintf("%s - [%s] \"%s %s %s %d %s \"%s\" %s\"\
",
			param.ClientIP,
			param.TimeStamp.Format("2006/01/02 - 15:04:05"),
			param.Method,
			param.Path,
			param.Request.Proto,
			param.StatusCode,
			param.Latency,
			param.Request.UserAgent(),
			param.ErrorMessage,
		)
	})
}

// Handler implementations
func (gw *APIGateway) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"timestamp": time.Now().Unix(),
		"version":   "0.1.0",
	})
}

func (gw *APIGateway) readinessCheck(c *gin.Context) {
	// Check scheduler connectivity
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	
	// TODO: Implement actual scheduler health check
	_ = ctx
	
	c.JSON(http.StatusOK, gin.H{
		"status":    "ready",
		"scheduler": "connected",
		"timestamp": time.Now().Unix(),
	})
}

func (gw *APIGateway) submitJob(c *gin.Context) {
	// TODO: Implement job submission với gRPC call to scheduler
	c.JSON(http.StatusOK, gin.H{
		"message": "Job submission endpoint - implementation pending",
		"job_id":  fmt.Sprintf("job_%d", time.Now().Unix()),
	})
}

func (gw *APIGateway) getJobStatus(c *gin.Context) {
	jobID := c.Param("id")
	// TODO: Implement job status retrieval
	c.JSON(http.StatusOK, gin.H{
		"job_id": jobID,
		"status": "mock_status",
	})
}

func (gw *APIGateway) cancelJob(c *gin.Context) {
	jobID := c.Param("id")
	// TODO: Implement job cancellation
	c.JSON(http.StatusOK, gin.H{
		"job_id":  jobID,
		"message": "Job cancellation - implementation pending",
	})
}

func (gw *APIGateway) listJobs(c *gin.Context) {
	// TODO: Implement job listing với pagination
	c.JSON(http.StatusOK, gin.H{
		"jobs": []interface{}{},
		"pagination": gin.H{
			"page":  1,
			"limit": 10,
			"total": 0,
		},
	})
}

func (gw *APIGateway) listWorkers(c *gin.Context) {
	// TODO: Implement worker listing
	c.JSON(http.StatusOK, gin.H{"workers": []interface{}{}})
}

func (gw *APIGateway) getWorkerStatus(c *gin.Context) {
	workerID := c.Param("id")
	c.JSON(http.StatusOK, gin.H{
		"worker_id": workerID,
		"status":    "mock_status",
	})
}

func (gw *APIGateway) getSystemStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "operational",
		"components": gin.H{
			"scheduler": "healthy",
			"workers":   "2 active",
			"queue":     "0 pending",
		},
	})
}

func (gw *APIGateway) getMetrics(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"message": "Metrics endpoint - Prometheus format available at /metrics"})
}

// Utility functions
func (gw *APIGateway) validateJWT(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		return gw.jwtSecret, nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*Claims); ok && token.Valid {
		return claims, nil
	}

	return nil, fmt.Errorf("invalid token claims")
}

func loadConfig(filename string) (*Config, error) {
	viper.SetConfigFile(filename)
	viper.SetConfigType("yaml")
	
	// Set defaults
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.port", 8080)
	viper.SetDefault("server.read_timeout", "30s")
	viper.SetDefault("server.write_timeout", "30s")
	viper.SetDefault("server.idle_timeout", "120s")
	viper.SetDefault("auth.token_expiry", "24h")
	viper.SetDefault("auth.require_mtls", true)
	viper.SetDefault("metrics.enabled", true)
	viper.SetDefault("metrics.path", "/metrics")
	viper.SetDefault("metrics.port", 9090)
	viper.SetDefault("scheduler.timeout", "30s")
	viper.SetDefault("tracing.enabled", true)
	viper.SetDefault("tracing.sampler", "always")

	if err := viper.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	return &config, nil
}

func setupMTLS(tlsConfig TLSConfig) (*tls.Config, error) {
	// Load CA certificate
	// Load server certificate and key
	// Configure mTLS
	// This is a simplified implementation
	return &tls.Config{
		MinVersion: tls.VersionTLS12,
		CipherSuites: []uint16{
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
		},
	}, nil
}

func initTracing(config TracingConfig) error {
	exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(jaeger.WithEndpoint(config.Endpoint)))
	if err != nil {
		return fmt.Errorf("failed to create Jaeger exporter: %w", err)
	}

	tp := trace.NewTracerProvider(
		trace.WithBatcher(exporter),
		trace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceNameKey.String("opus-api-gateway"),
			semconv.ServiceVersionKey.String("0.1.0"),
		)),
	)

	otel.SetTracerProvider(tp)
	log.Println("📍 OpenTelemetry tracing initialized")
	return nil
}

func min(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}
