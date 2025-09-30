// Package client - HTTP client implementation
// HTTPClient: HTTP REST client để query metrics và logs
package client

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// HTTPClient - HTTP client structure (REST client – client HTTP)
type HTTPClient struct {
	baseURL    string
	httpClient *http.Client
}

// MetricsQuery - Metrics query parameters (query params – tham số truy vấn)
type MetricsQuery struct {
	GPUID    int
	Duration time.Duration
}

// MetricValue - Single metric value (metric data point – điểm dữ liệu)
type MetricValue struct {
	Value     float64
	Labels    map[string]interface{}
	Timestamp time.Time
}

// LogQuery - Log query parameters (log filter – bộ lọc log)
type LogQuery struct {
	Tail   int
	Level  string
	Module string
	Since  time.Duration
	Follow bool
}

// LogEntry - Single log entry (log record – bản ghi log)
type LogEntry struct {
	Timestamp time.Time         `json:"timestamp"`
	Level     string            `json:"level"`
	Module    string            `json:"module"`
	Message   string            `json:"message"`
	Fields    map[string]interface{} `json:"fields,omitempty"`
}

// NewHTTPClient - Create HTTP client (client creation – tạo client mới)
func NewHTTPClient(baseURL string) *HTTPClient {
	return &HTTPClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// GetMetrics - Fetch Prometheus metrics (metrics retrieval – lấy metrics)
func (c *HTTPClient) GetMetrics(ctx context.Context, query *MetricsQuery) (map[string][]MetricValue, error) {
	url := fmt.Sprintf("%s/metrics", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Add query parameters
	q := req.URL.Query()
	if query.GPUID >= 0 {
		q.Add("gpu_id", fmt.Sprintf("%d", query.GPUID))
	}
	if query.Duration > 0 {
		q.Add("duration", query.Duration.String())
	}
	req.URL.RawQuery = q.Encode()

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	// Parse Prometheus format
	metrics, err := c.parsePrometheusMetrics(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to parse metrics: %w", err)
	}

	return metrics, nil
}

// parsePrometheusMetrics - Parse Prometheus text format (metrics parsing – phân tích metrics)
func (c *HTTPClient) parsePrometheusMetrics(r io.Reader) (map[string][]MetricValue, error) {
	metrics := make(map[string][]MetricValue)
	scanner := bufio.NewScanner(r)

	for scanner.Scan() {
		line := scanner.Text()

		// Skip comments và empty lines
		if len(line) == 0 || line[0] == '#' {
			continue
		}

		// Parse metric line: metric_name{labels} value timestamp
		// Example: gpu_temperature{gpu_id="0"} 65.5 1234567890
		name, value, labels, timestamp := c.parseMetricLine(line)
		if name == "" {
			continue
		}

		metrics[name] = append(metrics[name], MetricValue{
			Value:     value,
			Labels:    labels,
			Timestamp: timestamp,
		})
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("scanner error: %w", err)
	}

	return metrics, nil
}

// parseMetricLine - Parse single Prometheus metric line (line parsing – phân tích dòng)
func (c *HTTPClient) parseMetricLine(line string) (string, float64, map[string]interface{}, time.Time) {
	// Simplified parser - production code cần robust parser
	// Format: metric_name{label1="value1",label2="value2"} 123.45 1234567890

	var name string
	var value float64
	var timestamp int64
	labels := make(map[string]interface{})

	// Parse name và value (simplified)
	fmt.Sscanf(line, "%s %f %d", &name, &value, &timestamp)

	// Parse labels từ name (nếu có curly braces)
	// TODO: Implement proper label parsing

	ts := time.Unix(timestamp, 0)
	if timestamp == 0 {
		ts = time.Now()
	}

	return name, value, labels, ts
}

// StreamLogs - Stream logs từ miner (log streaming – stream log liên tục)
func (c *HTTPClient) StreamLogs(ctx context.Context, query *LogQuery) (<-chan *LogEntry, <-chan error) {
	logChan := make(chan *LogEntry, 100)
	errChan := make(chan error, 1)

	go func() {
		defer close(logChan)
		defer close(errChan)

		url := fmt.Sprintf("%s/logs", c.baseURL)
		req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
		if err != nil {
			errChan <- fmt.Errorf("failed to create request: %w", err)
			return
		}

		// Add query parameters
		q := req.URL.Query()
		if query.Tail > 0 {
			q.Add("tail", fmt.Sprintf("%d", query.Tail))
		}
		if query.Level != "" {
			q.Add("level", query.Level)
		}
		if query.Module != "" {
			q.Add("module", query.Module)
		}
		if query.Since > 0 {
			q.Add("since", query.Since.String())
		}
		if query.Follow {
			q.Add("follow", "true")
		}
		req.URL.RawQuery = q.Encode()

		resp, err := c.httpClient.Do(req)
		if err != nil {
			errChan <- fmt.Errorf("HTTP request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			errChan <- fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
			return
		}

		// Stream JSON lines
		decoder := json.NewDecoder(resp.Body)
		for {
			var entry LogEntry
			if err := decoder.Decode(&entry); err != nil {
				if err == io.EOF {
					return
				}
				errChan <- fmt.Errorf("decode error: %w", err)
				return
			}

			select {
			case logChan <- &entry:
			case <-ctx.Done():
				errChan <- ctx.Err()
				return
			}
		}
	}()

	return logChan, errChan
}

// GetHealth - Health check endpoint (health query – kiểm tra sức khỏe)
func (c *HTTPClient) GetHealth(ctx context.Context) (bool, error) {
	url := fmt.Sprintf("%s/health", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return false, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	return resp.StatusCode == http.StatusOK, nil
}
