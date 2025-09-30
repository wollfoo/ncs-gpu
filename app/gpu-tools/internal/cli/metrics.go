// Package cli - Metrics command implementation
// Metrics: Hiển thị Prometheus metrics từ miner
package cli

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/olekukonko/tablewriter"
	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var metricsCmd = &cobra.Command{
	Use:   "metrics [metric-name]",
	Short: "Display miner metrics",
	Long: `Query and display Prometheus metrics từ miner.
Hỗ trợ filter theo metric name, label, và time range.`,
	Example: `  gpu-ctl metrics
  gpu-ctl metrics gpu_temperature
  gpu-ctl metrics --gpu 0 --last 5m`,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		minerURL := rootCmd.PersistentFlags().Lookup("miner-url").Value.String()
		httpClient := client.NewHTTPClient(minerURL)

		gpuID, _ := cmd.Flags().GetInt("gpu")
		last, _ := cmd.Flags().GetDuration("last")

		// Fetch metrics từ Prometheus endpoint
		metrics, err := httpClient.GetMetrics(ctx, &client.MetricsQuery{
			GPUID:    gpuID,
			Duration: last,
		})
		if err != nil {
			return fmt.Errorf("failed to fetch metrics: %w", err)
		}

		// Filter by metric name nếu có args
		if len(args) > 0 {
			metrics = filterMetrics(metrics, args[0])
		}

		return displayMetrics(metrics)
	},
}

func init() {
	metricsCmd.Flags().Int("gpu", -1, "Filter by GPU ID (-1 for all)")
	metricsCmd.Flags().Duration("last", 5*time.Minute, "Time range")
	metricsCmd.Flags().Bool("raw", false, "Show raw Prometheus format")
}

// displayMetrics - Hiển thị metrics (metrics display – format đầu ra)
func displayMetrics(metrics map[string][]client.MetricValue) error {
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader([]string{"Metric", "GPU", "Value", "Timestamp"})
	table.SetBorder(false)

	for name, values := range metrics {
		for _, v := range values {
			table.Append([]string{
				name,
				fmt.Sprintf("%d", v.Labels["gpu_id"]),
				fmt.Sprintf("%.2f", v.Value),
				v.Timestamp.Format(time.RFC3339),
			})
		}
	}

	table.Render()
	return nil
}

// filterMetrics - Lọc metrics theo tên (metric filtering – lọc dữ liệu)
func filterMetrics(metrics map[string][]client.MetricValue, name string) map[string][]client.MetricValue {
	filtered := make(map[string][]client.MetricValue)
	for k, v := range metrics {
		if k == name {
			filtered[k] = v
		}
	}
	return filtered
}
