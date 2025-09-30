// Package main - GPU mining control CLI
// gpu-ctl: Command-line interface để quản lý OPUS-GPU miner
package main

import (
	"fmt"
	"os"

	"github.com/opus-gpu/gpu-tools/internal/cli"
)

func main() {
	if err := cli.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
