import { createClient, RedisClientType } from 'redis';
import { logger } from './logger';
import { WebhookPayload } from './validation';

export interface QueueMessage {
  id: string;
  payload: WebhookPayload;
  timestamp: Date;
  retries: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'dead_letter';
  lastAttempt?: Date;
  error?: string;
}

export interface QueueStats {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  deadLetter: number;
}

class RedisQueue {
  private client: RedisClientType;
  private publisher: RedisClientType;
  private subscriber: RedisClientType;
  private channelName: string;
  private statusKeyPrefix: string;
  private maxRetries: number;
  private retryDelayMs: number;
  private connected: boolean = false;
  
  constructor() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    
    // Main client for general operations
    this.client = createClient({ url: redisUrl });
    
    // Dedicated publisher client for pub/sub
    this.publisher = createClient({ url: redisUrl });
    
    // Dedicated subscriber client for pub/sub
    this.subscriber = createClient({ url: redisUrl });
    
    this.channelName = process.env.REDIS_CHANNEL_NAME || 'webhook_processing';
    this.statusKeyPrefix = process.env.REDIS_STATUS_PREFIX || 'webhook_status';
    this.maxRetries = parseInt(process.env.REDIS_MAX_RETRIES || '3', 10);
    this.retryDelayMs = parseInt(process.env.REDIS_RETRY_DELAY_MS || '1000', 10);
    
    // Error handlers
    this.client.on('error', (err) => {
      logger.error('Redis main client error', { error: err.message });
    });
    
    this.publisher.on('error', (err) => {
      logger.error('Redis publisher client error', { error: err.message });
    });
    
    this.subscriber.on('error', (err) => {
      logger.error('Redis subscriber client error', { error: err.message });
    });

    // Connection handlers
    this.client.on('connect', () => {
      logger.info('Redis main client connected');
    });
    
    this.publisher.on('connect', () => {
      logger.info('Redis publisher client connected');
    });
    
    this.subscriber.on('connect', () => {
      logger.info('Redis subscriber client connected');
    });
  }

  async connect(): Promise<void> {
    if (this.connected) {
      return;
    }

    try {
      await Promise.all([
        this.client.connect(),
        this.publisher.connect(),
        this.subscriber.connect()
      ]);
      
      this.connected = true;
      logger.info('All Redis clients connected successfully');
    } catch (error) {
      logger.error('Failed to connect Redis clients', { error: (error as Error).message });
      throw error;
    }
  }

  async publish(payload: WebhookPayload): Promise<string> {
    const messageId = this.generateMessageId(payload);
    let attempt = 0;
    
    while (attempt <= this.maxRetries) {
      try {
        await this.connect();
        
        const message: QueueMessage = {
          id: messageId,
          payload,
          timestamp: new Date(),
          retries: attempt,
          status: 'pending'
        };
        
        // Store message status
        await this.setMessageStatus(messageId, message);
        
        // Publish to channel
        const publishedCount = await this.publisher.publish(
          this.channelName, 
          JSON.stringify(message)
        );
        
        if (publishedCount === 0) {
          logger.warn('No subscribers listening to webhook channel', { 
            channel: this.channelName,
            messageId 
          });
        }
        
        logger.info('Published webhook to Redis pub/sub', {
          messageId,
          doctype: payload.doctype,
          docname: payload.docname,
          action: payload.action,
          attempt: attempt + 1,
          subscribers: publishedCount
        });
        
        return messageId;
        
      } catch (error) {
        attempt++;
        const isLastAttempt = attempt > this.maxRetries;
        
        logger.error('Failed to publish webhook to Redis', {
          error: (error as Error).message,
          messageId,
          attempt,
          isLastAttempt,
          payload: {
            doctype: payload.doctype,
            docname: payload.docname,
            action: payload.action
          }
        });
        
        if (isLastAttempt) {
          // Mark as failed in status tracking
          await this.setMessageStatus(messageId, {
            id: messageId,
            payload,
            timestamp: new Date(),
            retries: attempt - 1,
            status: 'failed',
            lastAttempt: new Date(),
            error: (error as Error).message
          }).catch(statusError => {
            logger.error('Failed to update message status after publish failure', {
              messageId,
              statusError: (statusError as Error).message
            });
          });
          
          throw error;
        }
        
        // Exponential backoff delay
        const delay = this.retryDelayMs * Math.pow(2, attempt - 1);
        logger.info(`Retrying webhook publish in ${delay}ms`, { messageId, attempt });
        await this.sleep(delay);
      }
    }
    
    throw new Error('Max retries exceeded for webhook publish');
  }

  async setMessageStatus(messageId: string, message: QueueMessage): Promise<void> {
    try {
      await this.connect();
      const statusKey = `${this.statusKeyPrefix}:${messageId}`;
      
      // Store with TTL of 24 hours
      await this.client.setEx(statusKey, 86400, JSON.stringify({
        ...message,
        lastUpdated: new Date()
      }));
      
      // Also maintain status counters
      await this.updateStatusCounters(message.status);
      
    } catch (error) {
      logger.error('Failed to set message status', {
        messageId,
        status: message.status,
        error: (error as Error).message
      });
      throw error;
    }
  }

  async getMessageStatus(messageId: string): Promise<QueueMessage | null> {
    try {
      await this.connect();
      const statusKey = `${this.statusKeyPrefix}:${messageId}`;
      const statusData = await this.client.get(statusKey);
      
      if (!statusData) {
        return null;
      }
      
      return JSON.parse(statusData);
    } catch (error) {
      logger.error('Failed to get message status', {
        messageId,
        error: (error as Error).message
      });
      return null;
    }
  }

  async updateMessageStatus(
    messageId: string, 
    status: QueueMessage['status'], 
    error?: string
  ): Promise<void> {
    try {
      const currentMessage = await this.getMessageStatus(messageId);
      if (!currentMessage) {
        logger.warn('Attempted to update status for non-existent message', { messageId });
        return;
      }
      
      const updatedMessage: QueueMessage = {
        ...currentMessage,
        status,
        lastAttempt: new Date(),
        error: error || currentMessage.error
      };
      
      await this.setMessageStatus(messageId, updatedMessage);
      
      logger.info('Updated message status', {
        messageId,
        oldStatus: currentMessage.status,
        newStatus: status,
        error
      });
      
    } catch (error) {
      logger.error('Failed to update message status', {
        messageId,
        status,
        error: (error as Error).message
      });
      throw error;
    }
  }

  async getQueueStats(): Promise<QueueStats> {
    try {
      await this.connect();
      
      const stats = await this.client.hGetAll(`${this.statusKeyPrefix}:counters`);
      
      return {
        pending: parseInt(stats.pending || '0', 10),
        processing: parseInt(stats.processing || '0', 10),
        completed: parseInt(stats.completed || '0', 10),
        failed: parseInt(stats.failed || '0', 10),
        deadLetter: parseInt(stats.dead_letter || '0', 10)
      };
    } catch (error) {
      logger.error('Failed to get queue stats', { error: (error as Error).message });
      return {
        pending: 0,
        processing: 0,
        completed: 0,
        failed: 0,
        deadLetter: 0
      };
    }
  }

  async subscribe(callback: (message: QueueMessage) => Promise<void>): Promise<void> {
    try {
      await this.connect();
      
      await this.subscriber.subscribe(this.channelName, async (messageData) => {
        try {
          const message: QueueMessage = JSON.parse(messageData);
          
          logger.info('Received webhook message from Redis pub/sub', {
            messageId: message.id,
            doctype: message.payload.doctype,
            docname: message.payload.docname,
            action: message.payload.action
          });
          
          // Update status to processing
          await this.updateMessageStatus(message.id, 'processing');
          
          // Execute callback
          await callback(message);
          
          // Update status to completed
          await this.updateMessageStatus(message.id, 'completed');
          
        } catch (error) {
          logger.error('Error processing webhook message', {
            error: (error as Error).message,
            messageData
          });
          
          // Try to extract message ID for status update
          try {
            const message: QueueMessage = JSON.parse(messageData);
            await this.updateMessageStatus(message.id, 'failed', (error as Error).message);
          } catch (parseError) {
            logger.error('Failed to parse message for error status update', {
              parseError: (parseError as Error).message
            });
          }
        }
      });
      
      logger.info('Subscribed to webhook processing channel', { channel: this.channelName });
      
    } catch (error) {
      logger.error('Failed to subscribe to webhook channel', {
        error: (error as Error).message,
        channel: this.channelName
      });
      throw error;
    }
  }

  async unsubscribe(): Promise<void> {
    try {
      await this.subscriber.unsubscribe(this.channelName);
      logger.info('Unsubscribed from webhook processing channel', { channel: this.channelName });
    } catch (error) {
      logger.error('Failed to unsubscribe from webhook channel', {
        error: (error as Error).message,
        channel: this.channelName
      });
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    if (!this.connected) {
      return;
    }

    try {
      await Promise.all([
        this.client.disconnect(),
        this.publisher.disconnect(),
        this.subscriber.disconnect()
      ]);
      
      this.connected = false;
      logger.info('All Redis clients disconnected');
    } catch (error) {
      logger.error('Error disconnecting Redis clients', { error: (error as Error).message });
      throw error;
    }
  }

  private generateMessageId(payload: WebhookPayload): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `${payload.doctype}_${payload.docname}_${payload.action}_${timestamp}_${random}`;
  }

  private async updateStatusCounters(status: QueueMessage['status']): Promise<void> {
    try {
      const counterKey = `${this.statusKeyPrefix}:counters`;
      await this.client.hIncrBy(counterKey, status, 1);
      
      // Set TTL on counters key (24 hours)
      await this.client.expire(counterKey, 86400);
    } catch (error) {
      logger.error('Failed to update status counters', {
        status,
        error: (error as Error).message
      });
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Health check method
  async isHealthy(): Promise<boolean> {
    try {
      await this.connect();
      await this.client.ping();
      return true;
    } catch (error) {
      logger.error('Redis health check failed', { error: (error as Error).message });
      return false;
    }
  }
}

export const redisQueue = new RedisQueue();
