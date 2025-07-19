import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';
import { webhookRouter } from './routes/webhook';
import { errorHandler } from './middleware/errorHandler';
import { logger } from './utils/logger';
import {
  requestContextMiddleware,
  metricsMiddleware,
  webhookMetricsMiddleware,
  errorTrackingMiddleware,
  getMetrics
} from './middleware/monitoring';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Request context middleware (must be first)
app.use(requestContextMiddleware);

// Metrics middleware
app.use(metricsMiddleware);

// Security middleware
app.use(helmet());
app.use(cors());

// Custom webhook metrics
app.use(webhookMetricsMiddleware);

// Parse JSON for non-webhook routes
app.use((req, res, next) => {
  if (req.path.startsWith('/webhooks')) {
    return next();
  }
  express.json()(req, res, next);
});

// Parse raw body for webhook signature verification
app.use('/webhooks', express.raw({ type: 'application/json' }));

// Health check endpoint with detailed status
app.get('/health', (req, res) => {
  const healthStatus = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'webhook-handler',
    version: '1.0.0',
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    environment: process.env.NODE_ENV || 'development'
  };
  
  logger.debug('Health check requested', { 
    request_id: req.context?.requestId,
    trace_id: req.context?.traceId 
  });
  
  res.json(healthStatus);
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  try {
    const metrics = await getMetrics();
    res.set('Content-Type', 'text/plain');
    res.send(metrics);
  } catch (error) {
    logger.error('Failed to get metrics', { 
      error,
      request_id: req.context?.requestId 
    });
    res.status(500).json({ error: 'Failed to get metrics' });
  }
});

// Webhook routes
app.use('/webhooks', webhookRouter);

// Error tracking middleware
app.use(errorTrackingMiddleware);

// Error handling
app.use(errorHandler);

const server = app.listen(PORT, () => {
  logger.info(`Webhook handler service listening on port ${PORT}`);
});

// Graceful shutdown handling
const gracefulShutdown = (signal: string) => {
  logger.info(`Received ${signal}. Starting graceful shutdown...`);
  
  const shutdownTimeout = parseInt(process.env.GRACEFUL_SHUTDOWN_TIMEOUT || '30000');
  
  server.close((err) => {
    if (err) {
      logger.error('Error during server shutdown:', err);
      process.exit(1);
    }
    
    logger.info('HTTP server closed');
    
    // Close Redis connections and other cleanup
    const cleanup = async () => {
      try {
        const { redisQueue } = await import('./utils/redis');
        await redisQueue.disconnect();
        logger.info('Redis connections closed');
        process.exit(0);
      } catch (error) {
        logger.error('Error during cleanup:', error);
        process.exit(1);
      }
    };
    
    cleanup();
  });
  
  // Force shutdown if graceful shutdown takes too long
  setTimeout(() => {
    logger.error('Graceful shutdown timeout exceeded. Forcing shutdown...');
    process.exit(1);
  }, shutdownTimeout);
};

// Handle shutdown signals
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception:', error);
  gracefulShutdown('uncaughtException');
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled rejection', { 
    reason: String(reason),
    promise: promise.toString()
  });
  gracefulShutdown('unhandledRejection');
});

export default app;