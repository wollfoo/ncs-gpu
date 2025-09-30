// Package config - Configuration management
// Config: Quản lý cấu hình từ file YAML/TOML
package config

import (
	"fmt"
	"os"

	"github.com/spf13/viper"
)

// Config - Main configuration structure (app config – cấu hình ứng dụng)
type Config struct {
	Miner  MinerConfig  `mapstructure:"miner"`
	Output OutputConfig `mapstructure:"output"`
	Alerts AlertConfig  `mapstructure:"alerts"`
}

// MinerConfig - Miner connection configuration (connection params – tham số kết nối)
type MinerConfig struct {
	URL      string `mapstructure:"url"`
	GRPCAddr string `mapstructure:"grpc_addr"`
	Timeout  int    `mapstructure:"timeout"`
}

// OutputConfig - Output formatting configuration (display settings – cài đặt hiển thị)
type OutputConfig struct {
	Format string `mapstructure:"format"` // table, json, yaml
	Color  bool   `mapstructure:"color"`
}

// AlertConfig - Alert rules configuration (alert rules – quy tắc cảnh báo)
type AlertConfig struct {
	Enabled bool        `mapstructure:"enabled"`
	Rules   []AlertRule `mapstructure:"rules"`
}

// AlertRule - Single alert rule (alert definition – định nghĩa cảnh báo)
type AlertRule struct {
	Name      string  `mapstructure:"name"`
	Metric    string  `mapstructure:"metric"`
	Operator  string  `mapstructure:"operator"` // >, <, ==, !=
	Threshold float64 `mapstructure:"threshold"`
	Action    string  `mapstructure:"action"` // webhook, email
	ActionURL string  `mapstructure:"action_url"`
}

// LoadConfig - Load configuration từ file (config loading – tải cấu hình)
func LoadConfig(path string) (*Config, error) {
	v := viper.New()

	if path != "" {
		// Use specified config file
		v.SetConfigFile(path)
	} else {
		// Search default locations
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, fmt.Errorf("cannot find home directory: %w", err)
		}

		v.AddConfigPath(home)
		v.AddConfigPath(".")
		v.SetConfigName(".gpu-ctl")
		v.SetConfigType("yaml")
	}

	// Set defaults
	setDefaults(v)

	// Environment variables
	v.SetEnvPrefix("GPUCTL")
	v.AutomaticEnv()

	// Read config file
	if err := v.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			// Config file not found - use defaults
			return &Config{
				Miner: MinerConfig{
					URL:      "http://localhost:8080",
					GRPCAddr: "localhost:9090",
					Timeout:  30,
				},
				Output: OutputConfig{
					Format: "table",
					Color:  true,
				},
				Alerts: AlertConfig{
					Enabled: false,
				},
			}, nil
		}
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	// Unmarshal config
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate config
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}

	return &cfg, nil
}

// setDefaults - Set default values (default config – cấu hình mặc định)
func setDefaults(v *viper.Viper) {
	v.SetDefault("miner.url", "http://localhost:8080")
	v.SetDefault("miner.grpc_addr", "localhost:9090")
	v.SetDefault("miner.timeout", 30)

	v.SetDefault("output.format", "table")
	v.SetDefault("output.color", true)

	v.SetDefault("alerts.enabled", false)
}

// Validate - Validate configuration (config validation – kiểm tra hợp lệ)
func (c *Config) Validate() error {
	// Validate miner URL
	if c.Miner.URL == "" {
		return fmt.Errorf("miner.url is required")
	}

	// Validate output format
	validFormats := map[string]bool{
		"table": true,
		"json":  true,
		"yaml":  true,
	}
	if !validFormats[c.Output.Format] {
		return fmt.Errorf("invalid output.format: %s (must be table, json, or yaml)", c.Output.Format)
	}

	// Validate alert rules
	if c.Alerts.Enabled {
		for i, rule := range c.Alerts.Rules {
			if err := rule.Validate(); err != nil {
				return fmt.Errorf("alert rule %d invalid: %w", i, err)
			}
		}
	}

	return nil
}

// Validate - Validate alert rule (rule validation – kiểm tra quy tắc)
func (r *AlertRule) Validate() error {
	if r.Name == "" {
		return fmt.Errorf("alert rule name is required")
	}

	if r.Metric == "" {
		return fmt.Errorf("alert rule metric is required")
	}

	validOperators := map[string]bool{
		">":  true,
		"<":  true,
		">=": true,
		"<=": true,
		"==": true,
		"!=": true,
	}
	if !validOperators[r.Operator] {
		return fmt.Errorf("invalid operator: %s", r.Operator)
	}

	validActions := map[string]bool{
		"webhook": true,
		"email":   true,
		"log":     true,
	}
	if !validActions[r.Action] {
		return fmt.Errorf("invalid action: %s", r.Action)
	}

	if r.Action == "webhook" && r.ActionURL == "" {
		return fmt.Errorf("action_url required for webhook action")
	}

	return nil
}
