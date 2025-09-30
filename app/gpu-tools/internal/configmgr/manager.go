// Package configmgr - Configuration manager với hot-reload
// ConfigManager: Watch config file changes và notify miner
package configmgr

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/xeipuuv/gojsonschema"
	"go.uber.org/zap"
	"gopkg.in/yaml.v3"
)

// Config - ConfigManager configuration (manager config – cấu hình quản lý)
type Config struct {
	ConfigPath  string
	SchemaPath  string
	GRPCAddr    string
	WatchPeriod time.Duration
}

// Manager - Configuration manager (config watcher – theo dõi cấu hình)
type Manager struct {
	config     *Config
	logger     *zap.Logger
	watcher    *fsnotify.Watcher
	grpcClient *client.GRPCClient
	schema     *gojsonschema.Schema
}

// NewManager - Create config manager (manager creation – tạo quản lý)
func NewManager(cfg *Config, logger *zap.Logger) (*Manager, error) {
	// Create file watcher
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, fmt.Errorf("failed to create watcher: %w", err)
	}

	// Load JSON schema nếu có
	var schema *gojsonschema.Schema
	if cfg.SchemaPath != "" {
		schemaLoader := gojsonschema.NewReferenceLoader("file://" + cfg.SchemaPath)
		schema, err = gojsonschema.NewSchema(schemaLoader)
		if err != nil {
			return nil, fmt.Errorf("failed to load schema: %w", err)
		}
	}

	// Create gRPC client
	grpcClient, err := client.NewGRPCClient(cfg.GRPCAddr)
	if err != nil {
		return nil, fmt.Errorf("failed to create gRPC client: %w", err)
	}

	return &Manager{
		config:     cfg,
		logger:     logger,
		watcher:    watcher,
		grpcClient: grpcClient,
		schema:     schema,
	}, nil
}

// Run - Start config manager (manager main loop – vòng lặp chính)
func (m *Manager) Run(ctx context.Context) error {
	// Watch config file
	if err := m.watcher.Add(m.config.ConfigPath); err != nil {
		return fmt.Errorf("failed to watch config file: %w", err)
	}

	m.logger.Info("Config manager started",
		zap.String("config_path", m.config.ConfigPath),
	)

	// Initial validation
	if err := m.validateAndReload(ctx); err != nil {
		m.logger.Error("Initial config validation failed", zap.Error(err))
	}

	for {
		select {
		case <-ctx.Done():
			m.logger.Info("Shutting down config manager")
			m.watcher.Close()
			m.grpcClient.Close()
			return nil

		case event, ok := <-m.watcher.Events:
			if !ok {
				return fmt.Errorf("watcher closed")
			}

			// Handle file write events
			if event.Op&fsnotify.Write == fsnotify.Write {
				m.logger.Info("Config file changed", zap.String("file", event.Name))

				// Debounce - wait for file writes to complete
				time.Sleep(100 * time.Millisecond)

				if err := m.validateAndReload(ctx); err != nil {
					m.logger.Error("Config reload failed", zap.Error(err))
				} else {
					m.logger.Info("Config reloaded successfully")
				}
			}

		case err, ok := <-m.watcher.Errors:
			if !ok {
				return fmt.Errorf("watcher closed")
			}
			m.logger.Error("Watcher error", zap.Error(err))
		}
	}
}

// validateAndReload - Validate và reload config (validation & reload – kiểm tra và tải lại)
func (m *Manager) validateAndReload(ctx context.Context) error {
	// Read config file
	data, err := os.ReadFile(m.config.ConfigPath)
	if err != nil {
		return fmt.Errorf("failed to read config: %w", err)
	}

	// Parse YAML
	var config map[string]interface{}
	if err := yaml.Unmarshal(data, &config); err != nil {
		return fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Validate against schema
	if m.schema != nil {
		if err := m.validateSchema(config); err != nil {
			return fmt.Errorf("schema validation failed: %w", err)
		}
	}

	// Notify miner via gRPC
	if err := m.notifyMiner(ctx, config); err != nil {
		return fmt.Errorf("failed to notify miner: %w", err)
	}

	return nil
}

// validateSchema - Validate config against JSON schema (schema validation – kiểm tra schema)
func (m *Manager) validateSchema(config map[string]interface{}) error {
	documentLoader := gojsonschema.NewGoLoader(config)

	result, err := m.schema.Validate(documentLoader)
	if err != nil {
		return fmt.Errorf("validation error: %w", err)
	}

	if !result.Valid() {
		// Collect validation errors
		var errors []string
		for _, err := range result.Errors() {
			errors = append(errors, err.String())
		}
		return fmt.Errorf("validation failed: %v", errors)
	}

	return nil
}

// notifyMiner - Notify miner về config changes (miner notification – thông báo miner)
func (m *Manager) notifyMiner(ctx context.Context, config map[string]interface{}) error {
	// Convert config to JSON bytes
	configBytes, err := yaml.Marshal(config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	// Call miner's ReloadConfig gRPC method
	req := &client.ReloadConfigRequest{
		ConfigYAML: string(configBytes),
	}

	if err := m.grpcClient.ReloadConfig(ctx, req); err != nil {
		return fmt.Errorf("gRPC ReloadConfig failed: %w", err)
	}

	m.logger.Info("Miner config reloaded successfully")
	return nil
}

// GetCurrentConfig - Lấy current config (config query – truy vấn cấu hình)
func (m *Manager) GetCurrentConfig() (map[string]interface{}, error) {
	data, err := os.ReadFile(m.config.ConfigPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var config map[string]interface{}
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	return config, nil
}

// UpdateConfig - Update config programmatically (config update – cập nhật cấu hình)
func (m *Manager) UpdateConfig(ctx context.Context, newConfig map[string]interface{}) error {
	// Validate first
	if m.schema != nil {
		if err := m.validateSchema(newConfig); err != nil {
			return fmt.Errorf("validation failed: %w", err)
		}
	}

	// Marshal to YAML
	data, err := yaml.Marshal(newConfig)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	// Write to file
	if err := os.WriteFile(m.config.ConfigPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	// File watcher sẽ tự động trigger reload

	m.logger.Info("Config updated",
		zap.String("path", m.config.ConfigPath),
	)

	return nil
}

// LoadSecretsFromVault - Load secrets từ HashiCorp Vault (secret loading – tải secrets)
func (m *Manager) LoadSecretsFromVault(ctx context.Context, vaultAddr, token string) error {
	// TODO: Implement Vault integration
	// Use github.com/hashicorp/vault/api

	m.logger.Info("Loading secrets from Vault",
		zap.String("vault_addr", vaultAddr),
	)

	// Example:
	// 1. Create Vault client
	// 2. Read secrets từ KV store
	// 3. Inject vào config
	// 4. Notify miner

	return nil
}

// LoadSecretsFromAWS - Load secrets từ AWS Secrets Manager (AWS secrets – secrets AWS)
func (m *Manager) LoadSecretsFromAWS(ctx context.Context, secretName string) error {
	// TODO: Implement AWS Secrets Manager integration
	// Use github.com/aws/aws-sdk-go-v2/service/secretsmanager

	m.logger.Info("Loading secrets from AWS Secrets Manager",
		zap.String("secret_name", secretName),
	)

	return nil
}
