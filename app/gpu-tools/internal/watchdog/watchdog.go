// Package watchdog - Miner health monitoring
// Watchdog: Giám sát và tự động restart miner khi unhealthy
package watchdog

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"sync"
	"syscall"
	"time"

	"go.uber.org/zap"
)

// Config - Watchdog configuration (watchdog config – cấu hình watchdog)
type Config struct {
	BinaryPath       string        // Path to miner binary
	Args             []string      // Command-line arguments
	HealthCheckURL   string        // HTTP health check endpoint
	CheckInterval    time.Duration // Health check frequency
	UnhealthyTimeout time.Duration // Grace period before restart
	MaxRestarts      int           // Max restart attempts (5 phút window)
	RestartBackoff   time.Duration // Backoff between restarts
	ShutdownTimeout  time.Duration // Graceful shutdown timeout
}

// Watchdog - Health monitoring daemon (monitoring daemon – daemon giám sát)
type Watchdog struct {
	config       *Config
	logger       *zap.Logger
	cmd          *exec.Cmd
	restartCount int
	restartTimes []time.Time
	mu           sync.Mutex
	httpClient   *http.Client
}

// ProcessState - Miner process state (process status – trạng thái tiến trình)
type ProcessState struct {
	Running       bool
	PID           int
	Uptime        time.Duration
	RestartCount  int
	LastRestart   time.Time
	HealthStatus  string
	UnhealthySince time.Time
}

// New - Create watchdog (watchdog creation – tạo watchdog)
func New(cfg *Config, logger *zap.Logger) *Watchdog {
	return &Watchdog{
		config: cfg,
		logger: logger,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
		restartTimes: make([]time.Time, 0, cfg.MaxRestarts),
	}
}

// Run - Start watchdog monitoring (watchdog main loop – vòng lặp chính)
func (w *Watchdog) Run(ctx context.Context) error {
	// Start miner initially
	if err := w.startMiner(ctx); err != nil {
		return fmt.Errorf("failed to start miner: %w", err)
	}

	ticker := time.NewTicker(w.config.CheckInterval)
	defer ticker.Stop()

	var unhealthySince time.Time

	for {
		select {
		case <-ctx.Done():
			w.logger.Info("Shutting down watchdog")
			return w.stopMiner()

		case <-ticker.C:
			healthy := w.checkHealth(ctx)

			if !healthy {
				if unhealthySince.IsZero() {
					unhealthySince = time.Now()
					w.logger.Warn("Miner became unhealthy")
				}

				// Check if exceeded unhealthy timeout
				if time.Since(unhealthySince) >= w.config.UnhealthyTimeout {
					w.logger.Error("Miner unhealthy timeout exceeded, restarting",
						zap.Duration("unhealthy_duration", time.Since(unhealthySince)),
					)

					if err := w.restartMiner(ctx); err != nil {
						w.logger.Error("Failed to restart miner", zap.Error(err))
					} else {
						unhealthySince = time.Time{} // Reset
					}
				}
			} else {
				if !unhealthySince.IsZero() {
					w.logger.Info("Miner recovered",
						zap.Duration("unhealthy_duration", time.Since(unhealthySince)),
					)
					unhealthySince = time.Time{}
				}
			}

			// Check if process exited
			if !w.isProcessRunning() {
				w.logger.Error("Miner process exited unexpectedly")
				if err := w.startMiner(ctx); err != nil {
					w.logger.Error("Failed to restart miner", zap.Error(err))
				}
			}
		}
	}
}

// startMiner - Khởi động miner process (process startup – khởi chạy tiến trình)
func (w *Watchdog) startMiner(ctx context.Context) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	// Check restart rate limiting
	if !w.canRestart() {
		return fmt.Errorf("restart rate limit exceeded (%d restarts in 5 minutes)",
			w.config.MaxRestarts)
	}

	w.logger.Info("Starting miner",
		zap.String("binary", w.config.BinaryPath),
		zap.Strings("args", w.config.Args),
	)

	// Create command
	w.cmd = exec.CommandContext(ctx, w.config.BinaryPath, w.config.Args...)
	w.cmd.Stdout = os.Stdout
	w.cmd.Stderr = os.Stderr

	// Set process group để kill toàn bộ child processes
	w.cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}

	// Start process
	if err := w.cmd.Start(); err != nil {
		return fmt.Errorf("failed to start process: %w", err)
	}

	w.logger.Info("Miner started", zap.Int("pid", w.cmd.Process.Pid))

	// Record restart
	w.restartTimes = append(w.restartTimes, time.Now())
	w.restartCount++

	return nil
}

// stopMiner - Dừng miner process gracefully (graceful shutdown – dừng nhẹ nhàng)
func (w *Watchdog) stopMiner() error {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.cmd == nil || w.cmd.Process == nil {
		return nil
	}

	pid := w.cmd.Process.Pid
	w.logger.Info("Stopping miner", zap.Int("pid", pid))

	// Send SIGTERM
	if err := w.cmd.Process.Signal(syscall.SIGTERM); err != nil {
		w.logger.Warn("Failed to send SIGTERM", zap.Error(err))
	}

	// Wait với timeout
	done := make(chan error, 1)
	go func() {
		done <- w.cmd.Wait()
	}()

	select {
	case err := <-done:
		if err != nil {
			w.logger.Warn("Miner exited with error", zap.Error(err))
		} else {
			w.logger.Info("Miner stopped gracefully")
		}
		return err

	case <-time.After(w.config.ShutdownTimeout):
		w.logger.Warn("Graceful shutdown timeout, force killing",
			zap.Int("pid", pid),
		)

		// Force kill entire process group
		pgid, err := syscall.Getpgid(pid)
		if err == nil {
			syscall.Kill(-pgid, syscall.SIGKILL)
		}

		return fmt.Errorf("forcefully killed after timeout")
	}
}

// restartMiner - Restart miner (restart operation – khởi động lại)
func (w *Watchdog) restartMiner(ctx context.Context) error {
	if err := w.stopMiner(); err != nil {
		w.logger.Warn("Error during stop", zap.Error(err))
	}

	// Backoff delay
	time.Sleep(w.config.RestartBackoff)

	return w.startMiner(ctx)
}

// checkHealth - Kiểm tra health status (health check – kiểm tra sức khỏe)
func (w *Watchdog) checkHealth(ctx context.Context) bool {
	req, err := http.NewRequestWithContext(ctx, "GET", w.config.HealthCheckURL, nil)
	if err != nil {
		w.logger.Error("Failed to create health check request", zap.Error(err))
		return false
	}

	resp, err := w.httpClient.Do(req)
	if err != nil {
		w.logger.Debug("Health check failed", zap.Error(err))
		return false
	}
	defer resp.Body.Close()

	healthy := resp.StatusCode == http.StatusOK
	if !healthy {
		w.logger.Debug("Health check unhealthy", zap.Int("status", resp.StatusCode))
	}

	return healthy
}

// isProcessRunning - Kiểm tra process có đang chạy không (process check – kiểm tra tiến trình)
func (w *Watchdog) isProcessRunning() bool {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.cmd == nil || w.cmd.Process == nil {
		return false
	}

	// Check if process exists
	process, err := os.FindProcess(w.cmd.Process.Pid)
	if err != nil {
		return false
	}

	// Send signal 0 to check existence
	err = process.Signal(syscall.Signal(0))
	return err == nil
}

// canRestart - Kiểm tra có thể restart không (rate limiting – giới hạn tốc độ)
func (w *Watchdog) canRestart() bool {
	now := time.Now()
	fiveMinutesAgo := now.Add(-5 * time.Minute)

	// Filter restarts trong 5 phút qua
	var recentRestarts []time.Time
	for _, t := range w.restartTimes {
		if t.After(fiveMinutesAgo) {
			recentRestarts = append(recentRestarts, t)
		}
	}

	w.restartTimes = recentRestarts

	return len(w.restartTimes) < w.config.MaxRestarts
}

// GetState - Lấy process state (state query – truy vấn trạng thái)
func (w *Watchdog) GetState() *ProcessState {
	w.mu.Lock()
	defer w.mu.Unlock()

	state := &ProcessState{
		RestartCount: w.restartCount,
	}

	if w.cmd != nil && w.cmd.Process != nil {
		state.Running = w.isProcessRunning()
		state.PID = w.cmd.Process.Pid
	}

	if len(w.restartTimes) > 0 {
		state.LastRestart = w.restartTimes[len(w.restartTimes)-1]
		state.Uptime = time.Since(state.LastRestart)
	}

	return state
}
