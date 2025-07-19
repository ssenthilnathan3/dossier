import { Router, Request, Response, NextFunction } from 'express';
import { WebhookValidator, WebhookPayload } from '../utils/validation';
import { createError } from '../middleware/errorHandler';
import { logger } from '../utils/logger';
import { redisQueue } from '../utils/redis';
import { trackRedisOperation } from '../middleware/monitoring';

const router = Router();

// Initialize webhook validator
const webhookSecret = process.env.WEBHOOK_SECRET;
if (!webhookSecret) {
  throw new Error('WEBHOOK_SECRET environment variable is required');
}

const validator = new WebhookValidator(webhookSecret);

/**
 * Frappe webhook endpoint
 */
router.post('/frappe', async (req: Request, res: Response, next: NextFunction) => {
  try {
    // Get raw body and signature
    const rawBody = req.body as Buffer;
    const signature = req.get('X-Frappe-Webhook-Signature') || req.get('X-Hub-Signature-256') || '';

    // Set logging context
    logger.setContext({
      request_id: req.context?.requestId,
      trace_id: req.context?.traceId,
      correlation_id: req.context?.correlationId
    });

    logger.info('Received webhook', {
      contentLength: rawBody.length,
      hasSignature: !!signature,
      userAgent: req.get('User-Agent'),
      operation: 'webhook_receive'
    });

    // Verify signature (skip in test environment)
    if (process.env.NODE_ENV !== 'test' && !validator.verifySignature(rawBody, signature)) {
      logger.warn('Webhook signature verification failed', {
        signature: signature.substring(0, 20) + '...',
        bodyLength: rawBody.length
      });
      throw createError('Invalid webhook signature', 401);
    }

    // Parse JSON payload
    let jsonPayload;
    try {
      jsonPayload = JSON.parse(rawBody.toString());
    } catch (error) {
      logger.error('Failed to parse webhook JSON', { error: (error as any).message });
      throw createError('Invalid JSON payload', 400);
    }

    // Validate payload structure
    let normalizedPayload: WebhookPayload;
    try {
      normalizedPayload = validator.validatePayload(jsonPayload);
    } catch (error) {
      logger.error('Payload validation failed', { error: (error as any).message, payload: jsonPayload });
      throw createError(`Payload validation failed: ${(error as any).message}`, 400);
    }

    // Check if we should process this doctype
    if (!validator.shouldProcessDoctype(normalizedPayload.doctype)) {
      logger.debug('Skipping webhook for system doctype', {
        doctype: normalizedPayload.doctype,
        docname: normalizedPayload.docname
      });
      
      return res.status(200).json({
        status: 'ignored',
        message: 'Doctype not configured for processing',
        doctype: normalizedPayload.doctype
      });
    }

    logger.info('Webhook validated successfully', {
      doctype: normalizedPayload.doctype,
      docname: normalizedPayload.docname,
      action: normalizedPayload.action
    });

    // Publish to Redis queue with monitoring
    try {
      const messageId = await trackRedisOperation('publish', () => 
        redisQueue.publish(normalizedPayload)
      );
      
      logger.info('Webhook queued successfully', {
        messageId,
        doctype: normalizedPayload.doctype,
        docname: normalizedPayload.docname,
        operation: 'webhook_queue'
      });
      
      res.status(200).json({
        status: 'queued',
        message: 'Webhook queued for processing',
        messageId,
        doctype: normalizedPayload.doctype,
        docname: normalizedPayload.docname,
        action: normalizedPayload.action,
        timestamp: normalizedPayload.timestamp
      });
    } catch (queueError) {
      logger.error('Failed to queue webhook', { 
        error: queueError,
        doctype: normalizedPayload.doctype,
        docname: normalizedPayload.docname,
        operation: 'webhook_queue_error'
      });
      throw createError('Failed to queue webhook for processing', 503);
    }

  } catch (error) {
    next(error);
  }
});

/**
 * Get webhook processing status by message ID
 */
router.get('/status/:messageId', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { messageId } = req.params;
    
    if (!messageId) {
      throw createError('Message ID is required', 400);
    }
    
    const status = await redisQueue.getMessageStatus(messageId);
    
    if (!status) {
      throw createError('Message not found', 404);
    }
    
    res.json({
      messageId,
      status: status.status,
      doctype: status.payload.doctype,
      docname: status.payload.docname,
      action: status.payload.action,
      timestamp: status.timestamp,
      retries: status.retries,
      lastAttempt: status.lastAttempt,
      error: status.error
    });
    
  } catch (error) {
    next(error);
  }
});

/**
 * Get queue statistics
 */
router.get('/stats', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const stats = await redisQueue.getQueueStats();
    
    res.json({
      queue: 'webhook_processing',
      stats,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    next(error);
  }
});

/**
 * Health check for webhook endpoint
 */
router.get('/health', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const redisHealthy = await redisQueue.isHealthy();
    
    res.json({
      status: redisHealthy ? 'healthy' : 'degraded',
      service: 'webhook-handler',
      timestamp: new Date().toISOString(),
      endpoints: ['/webhooks/frappe', '/webhooks/status/:messageId', '/webhooks/stats'],
      dependencies: {
        redis: redisHealthy ? 'healthy' : 'unhealthy'
      }
    });
    
  } catch (error) {
    next(error);
  }
});

export { router as webhookRouter };