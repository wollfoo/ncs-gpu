// Package cli - Logs command implementation
// Logs: Stream hoặc query logs từ miner
package cli

import (
	"context"
	"fmt"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var logsCmd = &cobra.Command{
	Use:   "logs",
	Short: "Stream or query miner logs",
	Long:  `Fetch và display logs từ miner. Hỗ trợ follow mode và filtering.`,
	Example: `  gpu-ctl logs --follow
  gpu-ctl logs --tail 100 --level error
  gpu-ctl logs --since 1h --module gpu.executor`,
	RunE: func(cmd *cobra.Command, args []string) error {
		follow, _ := cmd.Flags().GetBool("follow")
		tail, _ := cmd.Flags().GetInt("tail")
		level, _ := cmd.Flags().GetString("level")
		module, _ := cmd.Flags().GetString("module")
		since, _ := cmd.Flags().GetDuration("since")

		ctx := context.Background()
		if !follow {
			var cancel context.CancelFunc
			ctx, cancel = context.WithTimeout(ctx, 30*time.Second)
			defer cancel()
		}

		minerURL := rootCmd.PersistentFlags().Lookup("miner-url").Value.String()
		httpClient := client.NewHTTPClient(minerURL)

		query := &client.LogQuery{
			Tail:   tail,
			Level:  level,
			Module: module,
			Since:  since,
			Follow: follow,
		}

		logChan, errChan := httpClient.StreamLogs(ctx, query)

		// Print logs as they arrive
		for {
			select {
			case log, ok := <-logChan:
				if !ok {
					return nil
				}
				fmt.Println(formatLogEntry(log))
			case err := <-errChan:
				return fmt.Errorf("log stream error: %w", err)
			case <-ctx.Done():
				return ctx.Err()
			}
		}
	},
}

func init() {
	logsCmd.Flags().Bool("follow", false, "Follow log output")
	logsCmd.Flags().Int("tail", 100, "Number of lines to show")
	logsCmd.Flags().String("level", "", "Filter by log level (debug, info, warn, error)")
	logsCmd.Flags().String("module", "", "Filter by module name")
	logsCmd.Flags().Duration("since", 0, "Show logs since duration (e.g., 1h)")
}

// formatLogEntry - Format log entry (log formatting – định dạng log)
func formatLogEntry(log *client.LogEntry) string {
	timestamp := log.Timestamp.Format("2006-01-02 15:04:05")
	level := fmt.Sprintf("%-5s", log.Level)
	module := fmt.Sprintf("%-20s", log.Module)

	return fmt.Sprintf("[%s] %s %s %s", timestamp, level, module, log.Message)
}
