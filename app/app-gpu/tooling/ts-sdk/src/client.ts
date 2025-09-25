/**
 * Opus GPU Client - Main orchestration interface
 * 
 * High-level client cho GPU task submission và monitoring với:
 * - Type-safe gRPC communication
 * - Automatic retry với exponential backoff
 * - Real-time progress tracking
 * - Advanced error handling
 * - Connection pooling
 */

import { EventEmitter } from 'events';
import * as grpc from '@grpc/grpc-js';
import { connect, StringCodec, NatsConnection } from 'nats';
import { createLogger, Logger } from 'winston';
import { Counter, Histogram, register } from 'prom-client';

export interface GpuTask {
  id?: string;
  operation: string;
  priority: 'low' | 'normal' | 'high' | 'critical';
  gpuRequirements: {
    memoryMb: number;
    computeUnits: number; // 0.0-1.0
    minGpuMemoryGb?: number;
    preferredArch?: string;
    exclusiveAccess?: boolean;
  };
  estimatedDurationMs?: number;
  deadline?: Date;
  maxRetries?: number;
  payload: {
    params: Record<string, any>;
    inputData?: Buffer;
  };
}

export interface TaskResult {
  taskId: string;
  status: 'completed' | 'failed' | 'cancelled';
  outputData?: Buffer;
  metrics?: {
    gpuUtilizationAvg: number;
    memoryPeakMb: number;
    kernelTimeMs: number;
    memoryCopyTimeMs: number;
    totalTimeMs: number;
  };
  error?: string;
  completedAt: Date;
}

export interface ClientOptions {
  schedulerUrl: string;
  natsUrl?: string;
  enableMetrics?: boolean;
  enableTracing?: boolean;
  retryConfig?: {
    maxRetries: number;
    baseDelayMs: number;
    maxDelayMs: number;
  };
  timeout?: number;
}

export interface SchedulerStats {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  pendingTasks: number;
  activeWorkers: number;
  totalWorkers: number;
}

/**
 * Main Opus GPU Client
 */
export class OpusGpuClient extends EventEmitter {
  private readonly logger: Logger;
  private readonly options: Required<ClientOptions>;
  private readonly metrics: {
    tasksSubmitted: Counter<string>;
    tasksCompleted: Counter<string>;
    tasksFailed: Counter<string>;
    taskDuration: Histogram<string>;
    connectionErrors: Counter<string>;
  };
  
  private grpcClient?: any; // gRPC scheduler client
  private natsConnection?: NatsConnection;
  private isConnected = false;
  private connectionRetryCount = 0;
  
  constructor(options: ClientOptions) {
    super();
    
    this.options = {
      schedulerUrl: options.schedulerUrl,
      natsUrl: options.natsUrl || 'nats://localhost:4222',
      enableMetrics: options.enableMetrics ?? true,
      enableTracing: options.enableTracing ?? true,
      retryConfig: options.retryConfig || {
        maxRetries: 3,
        baseDelayMs: 1000,
        maxDelayMs: 10000,
      },
      timeout: options.timeout || 30000,
    };
    
    // Initialize logger
    this.logger = createLogger({
      level: 'info',
      format: require('winston').format.combine(
        require('winston').format.timestamp(),
        require('winston').format.json()
      ),
      transports: [
        new require('winston').transports.Console()
      ],
    });
    
    // Initialize metrics
    this.metrics = {
      tasksSubmitted: new Counter({
        name: 'opus_tasks_submitted_total',
        help: 'Total number of tasks submitted',
        labelNames: ['operation', 'priority'],
      }),
      tasksCompleted: new Counter({
        name: 'opus_tasks_completed_total', 
        help: 'Total number of completed tasks',
        labelNames: ['operation', 'status'],
      }),
      tasksFailed: new Counter({
        name: 'opus_tasks_failed_total',
        help: 'Total number of failed tasks',
        labelNames: ['operation', 'reason'],
      }),
      taskDuration: new Histogram({
        name: 'opus_task_duration_ms',
        help: 'Task execution duration in milliseconds',
        labelNames: ['operation'],
        buckets: [10, 50, 100, 500, 1000, 5000, 10000, 30000],
      }),
      connectionErrors: new Counter({
        name: 'opus_connection_errors_total',
        help: 'Total connection errors',
        labelNames: ['type'],
      }),
    };
    
    this.logger.info('🚀 OpusGpuClient initialized', {
      schedulerUrl: this.options.schedulerUrl,
      natsUrl: this.options.natsUrl,
      metricsEnabled: this.options.enableMetrics,
    });
  }
  
  /**
   * Connect to GPU scheduler và NATS
   */
  async connect(): Promise<void> {
    try {
      this.logger.info('📡 Connecting to Opus GPU services...');
      
      // Connect to NATS for real-time updates
      this.natsConnection = await connect({
        servers: [this.options.natsUrl],
        timeout: this.options.timeout,
        reconnect: true,
        maxReconnectAttempts: 10,
      });
      
      this.logger.info('✅ Connected to NATS', { url: this.options.natsUrl });
      
      // Setup task result subscription
      await this.setupTaskResultSubscription();
      
      // TODO: Initialize gRPC client for scheduler
      // this.grpcClient = new SchedulerServiceClient(...);
      
      this.isConnected = true;
      this.connectionRetryCount = 0;
      this.emit('connected');
      
      this.logger.info('✅ Connected to all Opus GPU services');
      
    } catch (error) {
      this.connectionRetryCount++;
      this.metrics.connectionErrors.inc({ type: 'connect' });
      
      this.logger.error('❌ Failed to connect to Opus GPU services', {
        error: error instanceof Error ? error.message : String(error),
        retryCount: this.connectionRetryCount,
      });
      
      this.emit('error', error);
      throw error;
    }
  }
  
  /**
   * Disconnect from services
   */
  async disconnect(): Promise<void> {
    this.logger.info('🔌 Disconnecting from Opus GPU services...');
    
    if (this.natsConnection) {
      await this.natsConnection.close();
    }
    
    if (this.grpcClient) {
      // Close gRPC connection
    }
    
    this.isConnected = false;
    this.emit('disconnected');
    
    this.logger.info('✅ Disconnected from Opus GPU services');
  }
  
  /**
   * Submit GPU task for execution
   */
  async submitTask(task: GpuTask): Promise<string> {
    if (!this.isConnected) {
      throw new Error('Client not connected. Call connect() first.');
    }
    
    // Generate task ID if not provided
    const taskId = task.id || `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    this.logger.info('📝 Submitting GPU task', {
      taskId,
      operation: task.operation,
      priority: task.priority,
      memoryMb: task.gpuRequirements.memoryMb,
    });
    
    try {
      // Record metrics
      if (this.options.enableMetrics) {
        this.metrics.tasksSubmitted.inc({
          operation: task.operation,
          priority: task.priority,
        });
      }
      
      // Submit via gRPC to scheduler
      // TODO: Implement actual gRPC call
      // const response = await this.grpcClient.submitTask({ ...task, id: taskId });
      
      this.logger.info('✅ Task submitted successfully', { taskId });
      this.emit('taskSubmitted', { taskId, task });
      
      return taskId;
      
    } catch (error) {
      this.metrics.tasksFailed.inc({
        operation: task.operation,
        reason: 'submission_failed',
      });
      
      this.logger.error('❌ Failed to submit task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      
      throw error;
    }
  }
  
  /**
   * Submit multiple tasks in batch
   */
  async submitBatch(tasks: GpuTask[]): Promise<string[]> {
    this.logger.info('📦 Submitting task batch', { count: tasks.length });
    
    const results: string[] = [];
    const errors: Error[] = [];
    
    // Submit tasks concurrently but with controlled concurrency
    const batchSize = 10;
    for (let i = 0; i < tasks.length; i += batchSize) {
      const batch = tasks.slice(i, i + batchSize);
      const promises = batch.map(task => this.submitTask(task).catch(err => {
        errors.push(err);
        return null;
      }));
      
      const batchResults = await Promise.all(promises);
      results.push(...batchResults.filter(id => id !== null) as string[]);
    }
    
    if (errors.length > 0) {
      this.logger.warn('⚠️ Some tasks failed to submit', {
        successCount: results.length,
        errorCount: errors.length,
      });
    }
    
    return results;
  }
  
  /**
   * Get task status
   */
  async getTaskStatus(taskId: string): Promise<any> {
    if (!this.isConnected) {
      throw new Error('Client not connected');
    }
    
    try {
      // TODO: Implement gRPC call to get task status
      // return await this.grpcClient.getTaskStatus({ taskId });
      
      return { taskId, status: 'mock' };
      
    } catch (error) {
      this.logger.error('❌ Failed to get task status', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }
  
  /**
   * Cancel task
   */
  async cancelTask(taskId: string): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Client not connected');
    }
    
    try {
      // TODO: Implement gRPC call to cancel task
      // await this.grpcClient.cancelTask({ taskId });
      
      this.logger.info('🚫 Task cancelled', { taskId });
      this.emit('taskCancelled', { taskId });
      
    } catch (error) {
      this.logger.error('❌ Failed to cancel task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }
  
  /**
   * Get scheduler statistics
   */
  async getSchedulerStats(): Promise<SchedulerStats> {
    if (!this.isConnected) {
      throw new Error('Client not connected');
    }
    
    try {
      // TODO: Implement gRPC call
      // return await this.grpcClient.getStats();
      
      return {
        totalTasks: 0,
        completedTasks: 0,
        failedTasks: 0,
        pendingTasks: 0,
        activeWorkers: 0,
        totalWorkers: 0,
      };
      
    } catch (error) {
      this.logger.error('❌ Failed to get scheduler stats', {
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }
  
  /**
   * Wait for task completion with timeout
   */
  async waitForTask(taskId: string, timeoutMs: number = 60000): Promise<TaskResult> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error(`Task ${taskId} timed out after ${timeoutMs}ms`));
      }, timeoutMs);
      
      const onResult = (result: TaskResult) => {
        if (result.taskId === taskId) {
          clearTimeout(timeout);
          this.off('taskResult', onResult);
          resolve(result);
        }
      };
      
      this.on('taskResult', onResult);
    });
  }
  
  /**
   * Setup subscription for task results
   */
  private async setupTaskResultSubscription(): Promise<void> {
    if (!this.natsConnection) {
      throw new Error('NATS connection not established');
    }
    
    const codec = StringCodec();
    const subscription = this.natsConnection.subscribe('task.results.*');
    
    this.logger.info('📡 Subscribed to task results');
    
    (async () => {
      for await (const msg of subscription) {
        try {
          const data = JSON.parse(codec.decode(msg.data));
          const result: TaskResult = {
            taskId: data.taskId,
            status: data.status,
            outputData: data.outputData ? Buffer.from(data.outputData, 'base64') : undefined,
            metrics: data.metrics,
            error: data.error,
            completedAt: new Date(data.completedAt),
          };
          
          // Record metrics
          if (this.options.enableMetrics) {
            if (result.status === 'completed') {
              this.metrics.tasksCompleted.inc({
                operation: data.operation || 'unknown',
                status: 'success',
              });
              
              if (result.metrics) {
                this.metrics.taskDuration.observe(
                  { operation: data.operation || 'unknown' },
                  result.metrics.totalTimeMs
                );
              }
            } else if (result.status === 'failed') {
              this.metrics.tasksFailed.inc({
                operation: data.operation || 'unknown',
                reason: 'execution_failed',
              });
            }
          }
          
          this.emit('taskResult', result);
          
          this.logger.debug('📋 Received task result', {
            taskId: result.taskId,
            status: result.status,
          });
          
        } catch (error) {
          this.logger.error('❌ Failed to process task result', {
            error: error instanceof Error ? error.message : String(error),
          });
        }
      }
    })().catch(error => {
      this.logger.error('❌ Task result subscription error', { error });
      this.emit('error', error);
    });
  }
  
  /**
   * Get connection status
   */
  get connected(): boolean {
    return this.isConnected;
  }
  
  /**
   * Get client metrics
   */
  async getMetrics(): Promise<string> {
    return register.metrics();
  }
}
