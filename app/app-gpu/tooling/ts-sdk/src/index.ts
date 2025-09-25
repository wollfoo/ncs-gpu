/**
 * Opus GPU TypeScript SDK
 * 
 * Comprehensive orchestration toolkit cho GPU processing với:
 * - Task submission và monitoring
 * - Performance benchmarking
 * - Resource management
 * - Advanced observability
 * - Configuration management
 */

export * from './client';
export * from './config';
export * from './monitoring';
export * from './benchmark';
export * from './types';
export * from './utils';

// Re-export main classes for convenience
export { OpusGpuClient } from './client';
export { ConfigManager } from './config';
export { MetricsCollector } from './monitoring';
export { BenchmarkSuite } from './benchmark';

// Version information
export const VERSION = '0.1.0';

/**
 * Quick start helper - creates configured client with sensible defaults
 */
export async function createOpusClient(options?: {
  schedulerUrl?: string;
  enableMetrics?: boolean;
  enableTracing?: boolean;
}): Promise<OpusGpuClient> {
  const { OpusGpuClient } = await import('./client');
  
  return new OpusGpuClient({
    schedulerUrl: options?.schedulerUrl || 'http://localhost:8080',
    enableMetrics: options?.enableMetrics ?? true,
    enableTracing: options?.enableTracing ?? true,
  });
}

/**
 * Performance benchmark helper
 */
export async function runQuickBenchmark(options?: {
  gpuCount?: number;
  duration?: number;
  taskType?: string;
}): Promise<any> {
  const { BenchmarkSuite } = await import('./benchmark');
  
  const suite = new BenchmarkSuite({
    gpuCount: options?.gpuCount || 1,
    duration: options?.duration || 60,
    taskType: options?.taskType || 'matrix_multiply',
  });
  
  return await suite.run();
}
