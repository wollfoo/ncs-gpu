package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/NVIDIA/go-nvml/pkg/nvml"
	"github.com/opus-gpu/app-gpu/internal/orchestrator"
	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	logger     = logrus.New()
	configFile string
	rootCmd    = &cobra.Command{
		Use:   "orchestrator",
		Short: "GPU Mining Orchestrator - điều phối khai thác GPU",
		Long:  `Orchestrator service quản lý và điều phối các GPU workers cho hệ thống khai thác`,
		Run:   runOrchestrator,
	}
)

func init() {
	cobra.OnInitialize(initConfig)
	rootCmd.PersistentFlags().StringVar(&configFile, "config", "", "config file (default: ./configs/orchestrator.yaml)")
	rootCmd.PersistentFlags().String("log-level", "info", "log level (debug, info, warn, error)")
	viper.BindPFlag("log.level", rootCmd.PersistentFlags().Lookup("log-level"))
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func initConfig() {
	if configFile != "" {
		viper.SetConfigFile(configFile)
	} else {
		viper.SetConfigName("orchestrator")
		viper.SetConfigType("yaml")
		viper.AddConfigPath("./configs")
		viper.AddConfigPath("/etc/gpu-mining")
	}
	
	viper.SetEnvPrefix("ORCHESTRATOR")
	viper.AutomaticEnv()
	
	// Default values
	viper.SetDefault("server.port", 8081)
	viper.SetDefault("workers.max_per_gpu", 2)
	viper.SetDefault("workers.restart_delay", "10s")
	viper.SetDefault("pool.url", "stratum+tcp://pool.woolypooly.com:55555")
	viper.SetDefault("monitoring.interval", "30s")
	viper.SetDefault("gpu.power_limit", 200) // watts
	viper.SetDefault("gpu.target_temp", 70)  // celsius
	
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			logger.Info("No config file found, using defaults")
		} else {
			logger.Warnf("Error reading config: %v", err)
		}
	}
	
	setupLogger()
}

func setupLogger() {
	level, err := logrus.ParseLevel(viper.GetString("log.level"))
	if err != nil {
		level = logrus.InfoLevel
	}
	logger.SetLevel(level)
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
		ForceColors:   true,
	})
}

func runOrchestrator(cmd *cobra.Command, args []string) {
	logger.Info("🚀 Starting GPU Mining Orchestrator...")
	
	// Initialize NVML
	if ret := nvml.Init(); ret != nvml.SUCCESS {
		logger.Fatalf("Failed to initialize NVML: %v", nvml.ErrorString(ret))
	}
	defer nvml.Shutdown()
	
	// Get GPU count
	count, ret := nvml.DeviceGetCount()
	if ret != nvml.SUCCESS {
		logger.Fatalf("Failed to get GPU count: %v", nvml.ErrorString(ret))
	}
	logger.Infof("✅ Detected %d GPU(s)", count)
	
	// Print GPU info
	for i := 0; i < count; i++ {
		device, ret := nvml.DeviceGetHandleByIndex(i)
		if ret != nvml.SUCCESS {
			logger.Errorf("Failed to get GPU %d: %v", i, nvml.ErrorString(ret))
			continue
		}
		
		name, _ := device.GetName()
		memInfo, _ := device.GetMemoryInfo()
		powerLimit, _ := device.GetPowerManagementLimit()
		
		logger.Infof("GPU %d: %s | Memory: %d MB | Power Limit: %d W", 
			i, name, memInfo.Total/1024/1024, powerLimit/1000)
	}
	
	// Create orchestrator
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	
	orch := orchestrator.New(orchestrator.Config{
		MaxWorkersPerGPU:  viper.GetInt("workers.max_per_gpu"),
		RestartDelay:      viper.GetDuration("workers.restart_delay"),
		PoolURL:          viper.GetString("pool.url"),
		WalletAddress:    viper.GetString("wallet.address"),
		WorkerNamePrefix: viper.GetString("worker.name_prefix"),
		GPUPowerLimit:    viper.GetInt("gpu.power_limit"),
		GPUTargetTemp:    viper.GetInt("gpu.target_temp"),
		MonitorInterval:  viper.GetDuration("monitoring.interval"),
	}, logger)
	
	// Start orchestrator
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := orch.Start(ctx); err != nil {
			logger.Errorf("Orchestrator error: %v", err)
		}
	}()
	
	// Start monitoring goroutine
	wg.Add(1)
	go func() {
		defer wg.Done()
		monitorGPUs(ctx, viper.GetDuration("monitoring.interval"))
	}()
	
	// Wait for shutdown signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigChan
	
	logger.Infof("🛑 Received signal %v, shutting down...", sig)
	
	// Cancel context to stop all goroutines
	cancel()
	
	// Wait for graceful shutdown
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()
	
	select {
	case <-done:
		logger.Info("✅ Orchestrator shutdown complete")
	case <-time.After(30 * time.Second):
		logger.Warn("⚠️ Shutdown timeout, forcing exit")
	}
}

func monitorGPUs(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			count, _ := nvml.DeviceGetCount()
			for i := 0; i < count; i++ {
				device, ret := nvml.DeviceGetHandleByIndex(i)
				if ret != nvml.SUCCESS {
					continue
				}
				
				// Get GPU metrics
				utilization, _ := device.GetUtilizationRates()
				temperature, _ := device.GetTemperature(nvml.TEMPERATURE_GPU)
				power, _ := device.GetPowerUsage()
				memInfo, _ := device.GetMemoryInfo()
				
				memUsedPercent := float64(memInfo.Used) / float64(memInfo.Total) * 100
				
				logger.WithFields(logrus.Fields{
					"gpu":         i,
					"util_gpu":    utilization.Gpu,
					"util_mem":    utilization.Memory,
					"temp":        temperature,
					"power":       power / 1000, // mW to W
					"mem_used":    memInfo.Used / 1024 / 1024, // bytes to MB
					"mem_percent": memUsedPercent,
				}).Debug("GPU metrics")
				
				// Check for thermal throttling
				if temperature > uint32(viper.GetInt("gpu.target_temp")) {
					logger.Warnf("⚠️ GPU %d temperature high: %d°C", i, temperature)
				}
			}
		}
	}
}
