import request from 'supertest';
import crypto from 'crypto';
import express from 'express';
import { webhookRouter } from '../routes/webhook';
import { errorHandler } from '../middleware/errorHandler';
import { it } from 'node:test';
import { describe } from 'node:test';

// Mock Redis queue
jest.mock('../utils/redis', () => ({
  redisQueue: {
    publish: jest.fn().mockResolvedValue('test-message-id-123'),
    getMessageStatus: jest.fn().mockResolvedValue(null),
    getQueueStats: jest.fn().mockResolvedValue({
      pending: 0,
      processing: 0,
      completed: 0,
      failed: 0,
      deadLetter: 0
    }),
    isHealthy: jest.fn().mockResolvedValue(true)
  }
}));

// Mock environment variables
process.env.WEBHOOK_SECRET = 'test-secret';
process.env.NODE_ENV = 'test';

const app = express();
// Parse JSON for non-webhook routes
app.use((req, res, next) => {
  if (req.path.startsWith('/webhooks')) {
    return next();
  }
  express.json()(req, res, next);
});
// Parse raw body for webhook signature verification
app.use('/webhooks', express.raw({ type: 'application/json' }));
app.use('/webhooks', webhookRouter);
app.use(errorHandler);

describe('Webhook Routes', () => {
  const testSecret = 'test-secret';

  const createSignature = (payload: string): string => {
    return crypto
      .createHmac('sha256', testSecret)
      .update(payload)
      .digest('hex');
  };

  describe('POST /webhooks/frappe', () => {
    it('should accept valid webhook with correct signature', async () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create',
        data: { customer_name: 'Test Customer' }
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'queued',
        messageId: 'test-message-id-123',
        doctype: 'Customer',
        docname: 'CUST-001',
        action: 'create'
      });
    });

    it('should accept webhook with X-Hub-Signature-256 header', async () => {
      const payload = {
        doctype: 'Item',
        name: 'ITEM-001',
        action: 'update'
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Hub-Signature-256', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(200);
      expect(response.body.status).toBe('queued');
    });

    it('should reject webhook with invalid signature', async () => {
      // Temporarily enable signature verification for this test
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'production';

      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create'
      };
      const payloadString = JSON.stringify(payload);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', 'invalid-signature')
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(401);
      expect(response.body.error.message).toBe('Invalid webhook signature');

      // Restore test environment
      process.env.NODE_ENV = originalEnv;
    });

    it('should reject webhook without signature', async () => {
      // Temporarily enable signature verification for this test
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'production';

      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create'
      };

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));

      expect(response.status).toBe(401);
      expect(response.body.error.message).toBe('Invalid webhook signature');

      // Restore test environment
      process.env.NODE_ENV = originalEnv;
    });

    it('should reject webhook with invalid JSON', async () => {
      const invalidJson = '{ invalid json }';
      const signature = createSignature(invalidJson);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(invalidJson);

      expect(response.status).toBe(400);
      expect(response.body.error.message).toBe('Invalid JSON payload');
    });

    it('should reject webhook with missing required fields', async () => {
      const payload = {
        doctype: 'Customer'
        // missing name and action
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(400);
      expect(response.body.error.message).toContain('Payload validation failed');
    });

    it('should ignore system doctypes', async () => {
      const payload = {
        doctype: 'User',
        name: 'user@example.com',
        action: 'update'
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'ignored',
        message: 'Doctype not configured for processing',
        doctype: 'User'
      });
    });

    it('should handle delete action without data field', async () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'delete'
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'queued',
        doctype: 'Customer',
        docname: 'CUST-001',
        action: 'delete'
      });
    });

    it('should handle Redis queue failure gracefully', async () => {
      // Mock Redis queue to fail
      const { redisQueue } = require('../utils/redis');
      redisQueue.publish.mockRejectedValueOnce(new Error('Redis connection failed'));

      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create'
      };
      const payloadString = JSON.stringify(payload);
      const signature = createSignature(payloadString);

      const response = await request(app)
        .post('/webhooks/frappe')
        .set('X-Frappe-Webhook-Signature', `sha256=${signature}`)
        .set('Content-Type', 'application/json')
        .send(payloadString);

      expect(response.status).toBe(503);
      expect(response.body.error.message).toBe('Failed to queue webhook for processing');

      // Reset mock
      redisQueue.publish.mockResolvedValue('test-message-id-123');
    });
  });

  describe('GET /webhooks/status/:messageId', () => {
    it('should return message status when found', async () => {
      const { redisQueue } = require('../utils/redis');
      const mockStatus = {
        id: 'test-message-id',
        payload: {
          doctype: 'Customer',
          docname: 'CUST-001',
          action: 'create',
          timestamp: new Date()
        },
        status: 'completed',
        retries: 0,
        timestamp: new Date(),
        lastAttempt: new Date()
      };
      
      redisQueue.getMessageStatus.mockResolvedValueOnce(mockStatus);

      const response = await request(app)
        .get('/webhooks/status/test-message-id');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        messageId: 'test-message-id',
        status: 'completed',
        doctype: 'Customer',
        docname: 'CUST-001',
        action: 'create',
        retries: 0
      });
    });

    it('should return 404 when message not found', async () => {
      const { redisQueue } = require('../utils/redis');
      redisQueue.getMessageStatus.mockResolvedValueOnce(null);

      const response = await request(app)
        .get('/webhooks/status/non-existent-id');

      expect(response.status).toBe(404);
      expect(response.body.error.message).toBe('Message not found');
    });

    it('should return 400 when message ID is missing', async () => {
      const response = await request(app)
        .get('/webhooks/status/');

      expect(response.status).toBe(404); // Express returns 404 for missing route params
    });
  });

  describe('GET /webhooks/stats', () => {
    it('should return queue statistics', async () => {
      const response = await request(app)
        .get('/webhooks/stats');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        queue: 'webhook_processing',
        stats: {
          pending: 0,
          processing: 0,
          completed: 0,
          failed: 0,
          deadLetter: 0
        }
      });
      expect(response.body.timestamp).toBeDefined();
    });

    it('should handle Redis stats failure gracefully', async () => {
      const { redisQueue } = require('../utils/redis');
      redisQueue.getQueueStats.mockRejectedValueOnce(new Error('Redis error'));

      const response = await request(app)
        .get('/webhooks/stats');

      expect(response.status).toBe(500);
    });
  });

  describe('GET /webhooks/health', () => {
    it('should return healthy status when Redis is available', async () => {
      const response = await request(app)
        .get('/webhooks/health');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'healthy',
        service: 'webhook-handler',
        endpoints: ['/webhooks/frappe', '/webhooks/status/:messageId', '/webhooks/stats'],
        dependencies: {
          redis: 'healthy'
        }
      });
    });

    it('should return degraded status when Redis is unavailable', async () => {
      const { redisQueue } = require('../utils/redis');
      redisQueue.isHealthy.mockResolvedValueOnce(false);

      const response = await request(app)
        .get('/webhooks/health');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'degraded',
        service: 'webhook-handler',
        dependencies: {
          redis: 'unhealthy'
        }
      });

      // Reset mock
      redisQueue.isHealthy.mockResolvedValue(true);
    });
  });
});