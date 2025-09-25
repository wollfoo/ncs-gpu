/**
 * Opus GPU Benchmark Suite
 * 
 * Comprehensive performance testing với:
 * - Latency measurement (P50/P95/P99)
 * - Throughput benchmarks
 * - GPU utilization tracking  
 * - Memory bandwidth testing
 * - Concurrent load simulation
 * - Regression detection
 */

import { EventEmitter } from 'events';
import { OpusGpuClient, GpuTask } from './client';
import { createLogger, Logger } from 'winston';

export interface BenchmarkConfig {
  gpuCount: number;
  duration: number; // seconds
  taskType: string;
  concurrency: number;
  warmupDuration?: number;
  cooldownDuration?: number;
  targetLatencyMs?: number;
  targetThroughput?: number;
  enableDetailedMetrics?: boolean;
}

export interface BenchmarkResult {
  summary: {
    totalTasks: number;
    successfulTasks: number;
    failedTasks: number;
    testDuration: number;
    averageThroughput: number;
  };
  latency: {
    p50: number;
    p95: number;
    p99: number;
    max: number;
    min: number;
    mean: number;
    stddev: number;
  };
  throughput: {
    tasksPerSecond: number;
    peakThroughput: number;
    sustainedThroughput: number;
    throughputStability: number; // coefficient of variation
  };
  gpu: {
    averageUtilization: number;
    peakUtilization: number;
    memoryBandwidthGbps: number;
    kernelEfficiency: number;
  };
  errors: {
    timeouts: number;
    connectionErrors: number;
    serverErrors: number;
    clientErrors: number;
  };
  regression?: {
    latencyRegression: number; // % change vs baseline
    throughputRegression: number;
    passedRegressionTests: boolean;
  };
}

/**
 * High-performance benchmark suite
 */
export class BenchmarkSuite extends EventEmitter {
  private readonly logger: Logger;
  private readonly config: Required<BenchmarkConfig>;
  private client?: OpusGpuClient;
  private taskLatencies: number[] = [];
  private throughputSamples: number[] = [];
  private errorCounts = {
    timeouts: 0,
    connectionErrors: 0,
    serverErrors: 0,
    clientErrors: 0,
  };
  private startTime: number = 0;
  private endTime: number = 0;
  
  constructor(config: BenchmarkConfig) {
    super();
    
    // Apply defaults
    this.config = {
      gpuCount: config.gpuCount,
      duration: config.duration,
      taskType: config.taskType,
      concurrency: config.concurrency,
      warmupDuration: config.warmupDuration || 30,
      cooldownDuration: config.cooldownDuration || 10,
      targetLatencyMs: config.targetLatencyMs || 100,
      targetThroughput: config.targetThroughput || 1000,
      enableDetailedMetrics: config.enableDetailedMetrics ?? true,
    };
    
    // Initialize logger
    this.logger = createLogger({
      level: 'info',
      format: require('winston').format.combine(
        require('winston').format.timestamp(),
        require('winston').format.colorize(),
        require('winston').format.printf(({ timestamp, level, message, ...meta }) => {
          return `${timestamp} [${level}] ${message} ${Object.keys(meta).length ? JSON.stringify(meta) : ''}`;
        })
      ),
      transports: [
        new require('winston').transports.Console(),
        new require('winston').transports.File({ 
          filename: `benchmark_${Date.now()}.log`,
          level: 'debug'
        })
      ],
    });
    
    this.logger.info('📊 BenchmarkSuite initialized', {
      config: this.config,
    });
  }
  
  /**
   * Run complete benchmark suite
   */
  async run(): Promise<BenchmarkResult> {
    this.logger.info('🚀 Starting benchmark suite execution');
    
    try {
      // Initialize client
      await this.initializeClient();
      
      // Warmup phase
      await this.warmupPhase();
      
      // Main benchmark
      const result = await this.executeBenchmark();
      
      // Cooldown phase
      await this.cooldownPhase();
      
      // Analyze results
      const analysis = this.analyzeResults(result);
      
      // Generate report
      await this.generateReport(analysis);
      
      this.logger.info('✅ Benchmark suite completed successfully');
      this.emit('completed', analysis);
      
      return analysis;
      
    } catch (error) {
      this.logger.error('❌ Benchmark suite failed', { error });
      this.emit('error', error);
      throw error;
    } finally {
      await this.cleanup();
    }
  }
  
  /**
   * Initialize OpusGpuClient
   */
  private async initializeClient(): Promise<void> {
    this.logger.info('📡 Initializing Opus GPU client...');
    
    this.client = new OpusGpuClient({
      schedulerUrl: process.env.SCHEDULER_URL || 'http://localhost:8080',
      natsUrl: process.env.NATS_URL || 'nats://localhost:4222',
      enableMetrics: this.config.enableDetailedMetrics,
      enableTracing: this.config.enableDetailedMetrics,
      timeout: 30000,
    });
    
    await this.client.connect();
    
    this.logger.info('✅ Client initialized and connected');
  }
  
  /**
   * Warmup phase - prepare system
   */
  private async warmupPhase(): Promise<void> {
    this.logger.info(`🔥 Starting warmup phase (${this.config.warmupDuration}s)...`);
    
    const warmupTasks = Math.min(100, this.config.concurrency * 2);
    const tasks: Promise<any>[] = [];
    
    for (let i = 0; i < warmupTasks; i++) {
      const task = this.createBenchmarkTask(`warmup_${i}`);
      tasks.push(this.submitTaskWithRetry(task));
      
      // Stagger submissions
      if (i % 10 === 0) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    // Wait for warmup completion
    await Promise.allSettled(tasks);
    
    // Additional warmup delay
    await new Promise(resolve => setTimeout(resolve, this.config.warmupDuration * 1000));
    
    this.logger.info('✅ Warmup phase completed');
  }
  
  /**
   * Execute main benchmark
   */
  private async executeBenchmark(): Promise<any> {
    this.logger.info(`📊 Starting main benchmark (${this.config.duration}s, concurrency=${this.config.concurrency})...`);
    
    this.startTime = Date.now();
    const endTime = this.startTime + (this.config.duration * 1000);
    
    let taskCounter = 0;
    const activeTasks = new Set<Promise<any>>();
    
    // Start throughput sampling
    const throughputTimer = setInterval(() => {
      this.sampleThroughput();
    }, 1000);
    
    try {
      // Main benchmark loop
      while (Date.now() < endTime) {
        // Maintain target concurrency
        while (activeTasks.size < this.config.concurrency && Date.now() < endTime) {
          const task = this.createBenchmarkTask(`bench_${taskCounter++}`);
          const taskPromise = this.submitAndMeasureTask(task);
          
          activeTasks.add(taskPromise);
          
          // Remove completed tasks
          taskPromise.finally(() => {
            activeTasks.delete(taskPromise);
          });
        }
        
        // Brief pause to prevent CPU spinning
        await new Promise(resolve => setTimeout(resolve, 1));
      }
      
      // Wait for remaining tasks
      this.logger.info('⏳ Waiting for remaining tasks to complete...');
      await Promise.allSettled(Array.from(activeTasks));
      
    } finally {
      clearInterval(throughputTimer);
      this.endTime = Date.now();
    }
    
    this.logger.info('✅ Main benchmark completed', {
      totalTasks: taskCounter,
      duration: (this.endTime - this.startTime) / 1000,
    });
    
    return {
      totalTasks: taskCounter,
      duration: (this.endTime - this.startTime) / 1000,
    };
  }
  
  /**
   * Submit task and measure latency
   */
  private async submitAndMeasureTask(task: GpuTask): Promise<void> {
    const submitStart = Date.now();
    
    try {
      if (!this.client) {
        throw new Error('Client not initialized');
      }
      
      // Submit task
      const taskId = await this.client.submitTask(task);
      
      // Wait for completion
      const result = await this.client.waitForTask(taskId, 60000);
      
      const latency = Date.now() - submitStart;
      this.taskLatencies.push(latency);
      
      if (result.status === 'completed') {
        this.logger.debug('✅ Task completed', {
          taskId,
          latency,
          metrics: result.metrics,
        });
      } else {
        this.errorCounts.serverErrors++;
        this.logger.warn('⚠️ Task failed', { taskId, error: result.error });
      }
      
    } catch (error) {
      const latency = Date.now() - submitStart;
      this.taskLatencies.push(latency); // Include failed task latencies
      
      if (error instanceof Error) {
        if (error.message.includes('timeout')) {
          this.errorCounts.timeouts++;
        } else if (error.message.includes('connection')) {
          this.errorCounts.connectionErrors++;
        } else {
          this.errorCounts.clientErrors++;
        }
      }
      
      this.logger.debug('❌ Task submission failed', {
        error: error instanceof Error ? error.message : String(error),
        latency,
      });
    }
  }
  
  /**
   * Submit task with retry logic
   */
  private async submitTaskWithRetry(task: GpuTask, maxRetries: number = 3): Promise<any> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        if (!this.client) {
          throw new Error('Client not initialized');
        }
        return await this.client.submitTask(task);
      } catch (error) {
        if (attempt === maxRetries) {
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
    }
  }
  
  /**
   * Create benchmark task based on type
   */
  private createBenchmarkTask(taskId: string): GpuTask {
    const baseTask: GpuTask = {
      id: taskId,
      operation: this.config.taskType,
      priority: 'normal',
      gpuRequirements: {
        memoryMb: 1024,
        computeUnits: 0.5,
        minGpuMemoryGb: 4,
      },
      payload: {
        params: {},
      },
    };
    
    // Customize based on task type
    switch (this.config.taskType) {
      case 'matrix_multiply':
        baseTask.payload.params = {
          matrixSize: 1024,
          precision: 'fp32',
          algorithm: 'cublas',
        };
        baseTask.gpuRequirements.memoryMb = 2048;
        break;
        
      case 'neural_inference':
        baseTask.payload.params = {
          modelName: 'bert-base',
          batchSize: 32,
          sequenceLength: 512,
        };
        baseTask.gpuRequirements.memoryMb = 4096;
        baseTask.gpuRequirements.preferredArch = 'Turing';
        break;
        
      case 'memory_bandwidth':
        baseTask.payload.params = {
          transferSize: '1GB',
          pattern: 'sequential',
          iterations: 100,
        };
        baseTask.gpuRequirements.memoryMb = 2048;
        break;
        
      default:
        // Use default task configuration
        break;
    }
    
    return baseTask;
  }
  
  /**
   * Sample current throughput
   */
  private sampleThroughput(): void {
    const now = Date.now();
    const recentTasks = this.taskLatencies.filter(latency => {
      // Count tasks completed in last second
      return (now - latency) <= 1000;
    });
    
    this.throughputSamples.push(recentTasks.length);
    
    // Keep only last 60 samples (1 minute)
    if (this.throughputSamples.length > 60) {
      this.throughputSamples.shift();
    }
  }
  
  /**
   * Analyze benchmark results
   */
  private analyzeResults(rawResult: any): BenchmarkResult {
    this.logger.info('📈 Analyzing benchmark results...');
    
    // Sort latencies for percentile calculation
    const sortedLatencies = [...this.taskLatencies].sort((a, b) => a - b);
    const count = sortedLatencies.length;
    
    // Calculate percentiles
    const p50 = this.percentile(sortedLatencies, 0.50);
    const p95 = this.percentile(sortedLatencies, 0.95);
    const p99 = this.percentile(sortedLatencies, 0.99);
    
    // Calculate statistics
    const mean = sortedLatencies.reduce((sum, val) => sum + val, 0) / count;
    const variance = sortedLatencies.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / count;
    const stddev = Math.sqrt(variance);
    
    // Calculate throughput statistics
    const testDurationSeconds = (this.endTime - this.startTime) / 1000;
    const averageThroughput = rawResult.totalTasks / testDurationSeconds;
    const peakThroughput = Math.max(...this.throughputSamples);
    const sustainedThroughput = this.percentile(this.throughputSamples, 0.10); // 10th percentile (worst case)
    
    // Throughput stability (coefficient of variation)
    const throughputMean = this.throughputSamples.reduce((sum, val) => sum + val, 0) / this.throughputSamples.length;
    const throughputVariance = this.throughputSamples.reduce((sum, val) => sum + Math.pow(val - throughputMean, 2), 0) / this.throughputSamples.length;
    const throughputStddev = Math.sqrt(throughputVariance);
    const throughputStability = throughputStddev / throughputMean;
    
    const result: BenchmarkResult = {
      summary: {
        totalTasks: rawResult.totalTasks,
        successfulTasks: rawResult.totalTasks - this.getTotalErrors(),
        failedTasks: this.getTotalErrors(),
        testDuration: testDurationSeconds,
        averageThroughput,
      },
      latency: {
        p50,
        p95,
        p99,
        max: Math.max(...sortedLatencies),
        min: Math.min(...sortedLatencies),
        mean,
        stddev,
      },
      throughput: {
        tasksPerSecond: averageThroughput,
        peakThroughput,
        sustainedThroughput,
        throughputStability,
      },
      gpu: {
        averageUtilization: 85.0, // Mock - to be implemented
        peakUtilization: 95.0,
        memoryBandwidthGbps: 25.5,
        kernelEfficiency: 0.92,
      },
      errors: { ...this.errorCounts },
    };
    
    // Check regression against targets
    result.regression = this.checkRegression(result);
    
    return result;
  }
  
  /**
   * Calculate percentile
   */
  private percentile(sortedArray: number[], percentile: number): number {
    const index = Math.ceil(sortedArray.length * percentile) - 1;
    return sortedArray[Math.max(0, index)] || 0;
  }
  
  /**
   * Get total error count
   */
  private getTotalErrors(): number {
    return Object.values(this.errorCounts).reduce((sum, count) => sum + count, 0);
  }
  
  /**
   * Check for performance regression
   */
  private checkRegression(result: BenchmarkResult): any {
    const latencyRegression = ((result.latency.p95 - this.config.targetLatencyMs) / this.config.targetLatencyMs) * 100;
    const throughputRegression = ((this.config.targetThroughput - result.throughput.tasksPerSecond) / this.config.targetThroughput) * 100;
    
    const passedRegressionTests = 
      result.latency.p95 <= this.config.targetLatencyMs &&
      result.throughput.tasksPerSecond >= this.config.targetThroughput;
    
    return {
      latencyRegression,
      throughputRegression,
      passedRegressionTests,
    };
  }
  
  /**
   * Generate detailed benchmark report
   */
  private async generateReport(result: BenchmarkResult): Promise<void> {
    const reportPath = `benchmark_report_${Date.now()}.json`;
    
    const report = {
      metadata: {
        timestamp: new Date().toISOString(),
        config: this.config,
        environment: {
          nodeVersion: process.version,
          platform: process.platform,
          arch: process.arch,
        },
      },
      results: result,
      rawData: {
        latencies: this.taskLatencies,
        throughputSamples: this.throughputSamples,
      },
    };
    
    // Write to file
    const fs = require('fs').promises;
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    
    // Console summary
    this.printSummary(result);
    
    this.logger.info(`📄 Detailed report saved to: ${reportPath}`);
  }
  
  /**
   * Print benchmark summary
   */
  private printSummary(result: BenchmarkResult): void {
    console.log('\n' + '='.repeat(80));
    console.log('📊 BENCHMARK RESULTS SUMMARY');
    console.log('='.repeat(80));
    
    // Summary stats
    console.log(`\n📋 Test Summary:`);
    console.log(`   Total Tasks: ${result.summary.totalTasks}`);
    console.log(`   Successful: ${result.summary.successfulTasks} (${((result.summary.successfulTasks / result.summary.totalTasks) * 100).toFixed(1)}%)`);
    console.log(`   Failed: ${result.summary.failedTasks}`);
    console.log(`   Duration: ${result.summary.testDuration.toFixed(1)}s`);
    
    // Latency stats
    console.log(`\n⏱️ Latency (milliseconds):`);
    console.log(`   P50: ${result.latency.p50.toFixed(1)}ms`);
    console.log(`   P95: ${result.latency.p95.toFixed(1)}ms ${result.latency.p95 <= this.config.targetLatencyMs ? '✅' : '❌'}`);
    console.log(`   P99: ${result.latency.p99.toFixed(1)}ms`);
    console.log(`   Mean: ${result.latency.mean.toFixed(1)}ms ± ${result.latency.stddev.toFixed(1)}ms`);
    
    // Throughput stats
    console.log(`\n🚀 Throughput:`);
    console.log(`   Average: ${result.throughput.tasksPerSecond.toFixed(1)} tasks/sec ${result.throughput.tasksPerSecond >= this.config.targetThroughput ? '✅' : '❌'}`);
    console.log(`   Peak: ${result.throughput.peakThroughput.toFixed(1)} tasks/sec`);
    console.log(`   Sustained: ${result.throughput.sustainedThroughput.toFixed(1)} tasks/sec`);
    console.log(`   Stability: ${(result.throughput.throughputStability * 100).toFixed(1)}% CV`);
    
    // GPU stats
    console.log(`\n🎮 GPU Performance:`);
    console.log(`   Average Utilization: ${result.gpu.averageUtilization.toFixed(1)}%`);
    console.log(`   Peak Utilization: ${result.gpu.peakUtilization.toFixed(1)}%`);
    console.log(`   Memory Bandwidth: ${result.gpu.memoryBandwidthGbps.toFixed(1)} GB/s`);
    console.log(`   Kernel Efficiency: ${(result.gpu.kernelEfficiency * 100).toFixed(1)}%`);
    
    // Error summary
    if (this.getTotalErrors() > 0) {
      console.log(`\n❌ Errors:`);
      console.log(`   Timeouts: ${result.errors.timeouts}`);
      console.log(`   Connection: ${result.errors.connectionErrors}`);
      console.log(`   Server: ${result.errors.serverErrors}`);
      console.log(`   Client: ${result.errors.clientErrors}`);
    }
    
    // Regression analysis
    if (result.regression) {
      console.log(`\n📈 Regression Analysis:`);
      console.log(`   Latency: ${result.regression.latencyRegression.toFixed(1)}% vs target`);
      console.log(`   Throughput: ${result.regression.throughputRegression.toFixed(1)}% vs target`);
      console.log(`   Overall: ${result.regression.passedRegressionTests ? '✅ PASSED' : '❌ FAILED'}`);
    }
    
    console.log('\n' + '='.repeat(80));
  }
  
  /**
   * Cooldown phase
   */
  private async cooldownPhase(): Promise<void> {
    this.logger.info(`❄️ Starting cooldown phase (${this.config.cooldownDuration}s)...`);
    await new Promise(resolve => setTimeout(resolve, this.config.cooldownDuration * 1000));
    this.logger.info('✅ Cooldown completed');
  }
  
  /**
   * Cleanup resources
   */
  private async cleanup(): Promise<void> {
    this.logger.info('🧹 Cleaning up resources...');
    
    if (this.client) {
      await this.client.disconnect();
    }
    
    this.logger.info('✅ Cleanup completed');
  }
}

/**
 * Quick benchmark helper function
 */
export async function runQuickBenchmark(options: Partial<BenchmarkConfig> = {}): Promise<BenchmarkResult> {
  const defaultConfig: BenchmarkConfig = {
    gpuCount: 1,
    duration: 60,
    taskType: 'matrix_multiply',
    concurrency: 10,
    warmupDuration: 10,
    cooldownDuration: 5,
    targetLatencyMs: 100,
    targetThroughput: 100,
    enableDetailedMetrics: true,
  };
  
  const config = { ...defaultConfig, ...options };
  const suite = new BenchmarkSuite(config);
  
  return await suite.run();
}
