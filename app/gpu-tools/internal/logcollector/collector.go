// Package logcollector - Centralized log collection
// LogCollector: Thu thập logs từ miner và export sang multiple sinks
package logcollector

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Config - LogCollector configuration (collector config – cấu hình thu thập)
type Config struct {
	Inputs  []InputConfig
	Outputs []OutputConfig
	BufferSize int
}

// InputConfig - Log input source (input config – cấu hình nguồn)
type InputConfig struct {
	Type string // file, stdout, http, syslog
	Path string // For file input
	URL  string // For HTTP input
}

// OutputConfig - Log output sink (output config – cấu hình đích)
type OutputConfig struct {
	Type   string // file, loki, elasticsearch, stdout
	Path   string // For file output
	URL    string // For Loki/ES
	Format string // json, text
}

// LogEntry - Structured log entry (log record – bản ghi log)
type LogEntry struct {
	Timestamp time.Time              `json:"timestamp"`
	Level     string                 `json:"level"`
	Module    string                 `json:"module"`
	Message   string                 `json:"message"`
	Fields    map[string]interface{} `json:"fields,omitempty"`
	Source    string                 `json:"source"` // Input source
}

// LogCollector - Log collection service (collector service – dịch vụ thu thập)
type LogCollector struct {
	config  *Config
	logger  *zap.Logger
	inputs  []LogInput
	outputs []LogSink
	buffer  chan *LogEntry
	wg      sync.WaitGroup
}

// LogInput - Log input interface (input interface – giao diện nguồn)
type LogInput interface {
	Read(ctx context.Context, ch chan<- *LogEntry) error
	Close() error
}

// LogSink - Log output interface (sink interface – giao diện đích)
type LogSink interface {
	Write(ctx context.Context, entry *LogEntry) error
	Flush() error
	Close() error
}

// NewCollector - Create log collector (collector creation – tạo bộ thu thập)
func NewCollector(cfg *Config, logger *zap.Logger) (*LogCollector, error) {
	if cfg.BufferSize == 0 {
		cfg.BufferSize = 1000
	}

	collector := &LogCollector{
		config:  cfg,
		logger:  logger,
		buffer:  make(chan *LogEntry, cfg.BufferSize),
		inputs:  make([]LogInput, 0),
		outputs: make([]LogSink, 0),
	}

	// Initialize inputs
	for _, inputCfg := range cfg.Inputs {
		input, err := createInput(inputCfg)
		if err != nil {
			return nil, fmt.Errorf("failed to create input: %w", err)
		}
		collector.inputs = append(collector.inputs, input)
	}

	// Initialize outputs
	for _, outputCfg := range cfg.Outputs {
		sink, err := createSink(outputCfg)
		if err != nil {
			return nil, fmt.Errorf("failed to create sink: %w", err)
		}
		collector.outputs = append(collector.outputs, sink)
	}

	return collector, nil
}

// Run - Start log collector (collector main loop – vòng lặp chính)
func (c *LogCollector) Run(ctx context.Context) error {
	c.logger.Info("Log collector started",
		zap.Int("inputs", len(c.inputs)),
		zap.Int("outputs", len(c.outputs)),
	)

	// Start input readers
	for _, input := range c.inputs {
		c.wg.Add(1)
		go func(in LogInput) {
			defer c.wg.Done()
			if err := in.Read(ctx, c.buffer); err != nil {
				c.logger.Error("Input read error", zap.Error(err))
			}
		}(input)
	}

	// Start log processor
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		c.processLogs(ctx)
	}()

	// Wait for context cancellation
	<-ctx.Done()

	// Cleanup
	c.logger.Info("Shutting down log collector")
	close(c.buffer)
	c.wg.Wait()

	// Flush and close all outputs
	for _, sink := range c.outputs {
		sink.Flush()
		sink.Close()
	}

	return nil
}

// processLogs - Process logs từ buffer (log processing – xử lý log)
func (c *LogCollector) processLogs(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return

		case entry, ok := <-c.buffer:
			if !ok {
				return
			}

			// Write to all sinks
			for _, sink := range c.outputs {
				if err := sink.Write(ctx, entry); err != nil {
					c.logger.Error("Sink write error",
						zap.Error(err),
						zap.String("message", entry.Message),
					)
				}
			}
		}
	}
}

// ============================================================================
// File Input
// ============================================================================

// FileInput - File log input (file reader – đọc từ file)
type FileInput struct {
	path   string
	file   *os.File
	parser LogParser
}

// NewFileInput - Create file input (file input creation – tạo đầu vào file)
func NewFileInput(path string) (*FileInput, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}

	return &FileInput{
		path:   path,
		file:   file,
		parser: &JSONLogParser{},
	}, nil
}

// Read - Read logs from file (file reading – đọc file)
func (f *FileInput) Read(ctx context.Context, ch chan<- *LogEntry) error {
	scanner := bufio.NewScanner(f.file)

	for scanner.Scan() {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		line := scanner.Text()
		entry, err := f.parser.Parse(line)
		if err != nil {
			continue // Skip invalid lines
		}

		entry.Source = f.path

		select {
		case ch <- entry:
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return scanner.Err()
}

// Close - Close file (cleanup – dọn dẹp)
func (f *FileInput) Close() error {
	return f.file.Close()
}

// ============================================================================
// Stdout Input (for Docker containers)
// ============================================================================

// StdoutInput - Stdout log input (stdout reader – đọc từ stdout)
type StdoutInput struct {
	reader io.Reader
	parser LogParser
}

// NewStdoutInput - Create stdout input (stdout input creation – tạo đầu vào stdout)
func NewStdoutInput() *StdoutInput {
	return &StdoutInput{
		reader: os.Stdin,
		parser: &JSONLogParser{},
	}
}

// Read - Read logs từ stdout (stdout reading – đọc stdout)
func (s *StdoutInput) Read(ctx context.Context, ch chan<- *LogEntry) error {
	scanner := bufio.NewScanner(s.reader)

	for scanner.Scan() {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		line := scanner.Text()
		entry, err := s.parser.Parse(line)
		if err != nil {
			continue
		}

		entry.Source = "stdout"

		select {
		case ch <- entry:
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return scanner.Err()
}

// Close - Close stdin
func (s *StdoutInput) Close() error {
	return nil
}

// ============================================================================
// File Output
// ============================================================================

// FileSink - File log output (file writer – ghi vào file)
type FileSink struct {
	path   string
	file   *os.File
	format string
	mu     sync.Mutex
}

// NewFileSink - Create file sink (file sink creation – tạo đầu ra file)
func NewFileSink(path, format string) (*FileSink, error) {
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}

	return &FileSink{
		path:   path,
		file:   file,
		format: format,
	}, nil
}

// Write - Write log entry (file writing – ghi file)
func (f *FileSink) Write(ctx context.Context, entry *LogEntry) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	var line string
	if f.format == "json" {
		data, err := json.Marshal(entry)
		if err != nil {
			return fmt.Errorf("failed to marshal entry: %w", err)
		}
		line = string(data) + "\n"
	} else {
		// Text format
		line = fmt.Sprintf("[%s] %s %s: %s\n",
			entry.Timestamp.Format(time.RFC3339),
			entry.Level,
			entry.Module,
			entry.Message,
		)
	}

	_, err := f.file.WriteString(line)
	return err
}

// Flush - Flush buffer
func (f *FileSink) Flush() error {
	return f.file.Sync()
}

// Close - Close file
func (f *FileSink) Close() error {
	return f.file.Close()
}

// ============================================================================
// Stdout Sink
// ============================================================================

// StdoutSink - Stdout log output (stdout writer – ghi stdout)
type StdoutSink struct {
	format string
}

// NewStdoutSink - Create stdout sink (stdout sink creation – tạo đầu ra stdout)
func NewStdoutSink(format string) *StdoutSink {
	return &StdoutSink{format: format}
}

// Write - Write to stdout (stdout writing – ghi stdout)
func (s *StdoutSink) Write(ctx context.Context, entry *LogEntry) error {
	if s.format == "json" {
		data, err := json.Marshal(entry)
		if err != nil {
			return err
		}
		fmt.Println(string(data))
	} else {
		fmt.Printf("[%s] %s %s: %s\n",
			entry.Timestamp.Format(time.RFC3339),
			entry.Level,
			entry.Module,
			entry.Message,
		)
	}
	return nil
}

// Flush - No-op for stdout
func (s *StdoutSink) Flush() error {
	return nil
}

// Close - No-op for stdout
func (s *StdoutSink) Close() error {
	return nil
}

// ============================================================================
// Log Parser
// ============================================================================

// LogParser - Log parsing interface (parser interface – giao diện phân tích)
type LogParser interface {
	Parse(line string) (*LogEntry, error)
}

// JSONLogParser - JSON log parser (JSON parser – phân tích JSON)
type JSONLogParser struct{}

// Parse - Parse JSON log line (JSON parsing – phân tích JSON)
func (p *JSONLogParser) Parse(line string) (*LogEntry, error) {
	var entry LogEntry
	if err := json.Unmarshal([]byte(line), &entry); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}
	return &entry, nil
}

// ============================================================================
// Helper Functions
// ============================================================================

// createInput - Create input từ config (input factory – tạo đầu vào)
func createInput(cfg InputConfig) (LogInput, error) {
	switch cfg.Type {
	case "file":
		return NewFileInput(cfg.Path)
	case "stdout":
		return NewStdoutInput(), nil
	default:
		return nil, fmt.Errorf("unknown input type: %s", cfg.Type)
	}
}

// createSink - Create sink từ config (sink factory – tạo đầu ra)
func createSink(cfg OutputConfig) (LogSink, error) {
	switch cfg.Type {
	case "file":
		return NewFileSink(cfg.Path, cfg.Format)
	case "stdout":
		return NewStdoutSink(cfg.Format), nil
	default:
		return nil, fmt.Errorf("unknown sink type: %s", cfg.Type)
	}
}
