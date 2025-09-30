// Package cli - Cobra root command implementation
// Root command: Entry point cho gpu-ctl CLI với global flags
package cli

import (
	"fmt"
	"os"

	"github.com/opus-gpu/gpu-tools/internal/config"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile string
	cfg     *config.Config
)

// rootCmd - Root command định nghĩa (Cobra root – CLI entry point)
var rootCmd = &cobra.Command{
	Use:   "gpu-ctl",
	Short: "OPUS-GPU Mining Control CLI",
	Long: `gpu-ctl là công cụ dòng lệnh để quản lý, giám sát và điều khiển
GPU mining operations. Hỗ trợ start/stop miner, metrics monitoring,
GPU statistics, và stealth mode configuration.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Load configuration trước khi chạy bất kỳ subcommand nào
		var err error
		cfg, err = config.LoadConfig(cfgFile)
		if err != nil {
			return fmt.Errorf("failed to load config: %w", err)
		}
		return nil
	},
}

// Execute - Thực thi root command (CLI execution – khởi chạy CLI)
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags cho tất cả subcommands
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "",
		"config file path (default: $HOME/.gpu-ctl.yaml)")
	rootCmd.PersistentFlags().String("miner-url", "http://localhost:8080",
		"Miner HTTP API URL")
	rootCmd.PersistentFlags().String("grpc-addr", "localhost:9090",
		"Miner gRPC address")
	rootCmd.PersistentFlags().String("output", "table",
		"Output format: table, json, yaml")

	// Bind flags to viper để support environment variables
	viper.BindPFlag("miner.url", rootCmd.PersistentFlags().Lookup("miner-url"))
	viper.BindPFlag("miner.grpc_addr", rootCmd.PersistentFlags().Lookup("grpc-addr"))
	viper.BindPFlag("output.format", rootCmd.PersistentFlags().Lookup("output"))

	// Register subcommands
	rootCmd.AddCommand(startCmd)
	rootCmd.AddCommand(stopCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(metricsCmd)
	rootCmd.AddCommand(logsCmd)
	rootCmd.AddCommand(stealthCmd)
	rootCmd.AddCommand(gpuCmd)
}

// initConfig - Khởi tạo configuration (config initialization – đọc file cấu hình)
func initConfig() {
	if cfgFile != "" {
		// Sử dụng config file được chỉ định
		viper.SetConfigFile(cfgFile)
	} else {
		// Search config in home directory
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: Cannot find home directory: %v\n", err)
			return
		}

		viper.AddConfigPath(home)
		viper.AddConfigPath(".")
		viper.SetConfigType("yaml")
		viper.SetConfigName(".gpu-ctl")
	}

	// Environment variable prefix
	viper.SetEnvPrefix("GPUCTL")
	viper.AutomaticEnv()

	// Read config file nếu tồn tại
	if err := viper.ReadInConfig(); err == nil {
		fmt.Fprintf(os.Stderr, "Using config file: %s\n", viper.ConfigFileUsed())
	}
}
