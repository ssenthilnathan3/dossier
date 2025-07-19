/**
 * Monitoring middleware for webhook handler service
 */
import { Request, Response, NextFunction } from "express";
import { v4 as uuidv4 } from "uuid";
import promBundle from "express-prom-bundle";
import client from "prom-client";

// Custom metrics
const webhookProcessingDuration = new client.Histogram({
  name: "webhook_processing_duration_seconds",
  help: "Duration of webhook processing",
  labelNames: ["method", "status", "webhook_type"],
});

const webhookValidationErrors = new client.Counter({
  name: "webhook_validation_errors_total",
  help: "Total number of webhook validation errors",
  labelNames: ["error_type"],
});

const redisOperations = new client.Histogram({
  name: "redis_operation_duration_seconds",
  help: "Duration of Redis operations",
  labelNames: ["operation", "status"],
});

const activeConnections = new client.Gauge({
  name: "active_connections",
  help: "Number of active connections",
});

// Request context interface
interface RequestContext {
  requestId: string;
  traceId: string;
  startTime: number;
  correlationId?: string;
}

// Extend Express Request type
declare global {
  namespace Express {
    interface Request {
      context: RequestContext;
    }
  }
}

/**
 * Request context middleware - adds request ID and trace ID
 */
export const requestContextMiddleware = (
  req: Request,
  res: Response,
  next: NextFunction,
) => {
  const requestId = uuidv4();
  const traceId = (req.headers["x-trace-id"] as string) || uuidv4();
  const correlationId = req.headers["x-correlation-id"] as string;

  req.context = {
    requestId,
    traceId,
    startTime: Date.now(),
    correlationId,
  };

  // Add trace headers to response
  res.setHeader("X-Request-Id", requestId);
  res.setHeader("X-Trace-Id", traceId);

  next();
};

/**
 * Prometheus metrics middleware
 */
export const metricsMiddleware = promBundle({
  includeMethod: true,
  includePath: true,
  includeStatusCode: true,
  includeUp: true,
  customLabels: {
    service: "webhook-handler",
  },
  promClient: {
    collectDefaultMetrics: {},
  },
});

/**
 * Custom webhook metrics middleware
 */
export const webhookMetricsMiddleware = (
  req: Request,
  res: Response,
  next: NextFunction,
) => {
  const startTime = Date.now();

  // Track active connections
  activeConnections.inc();

  res.on("finish", () => {
    const duration = (Date.now() - startTime) / 1000;
    const webhookType = req.body?.doctype || "unknown";

    webhookProcessingDuration
      .labels(req.method, res.statusCode.toString(), webhookType)
      .observe(duration);

    activeConnections.dec();
  });

  next();
};

/**
 * Error tracking middleware
 */
export const errorTrackingMiddleware = (
  error: Error,
  req: Request,
  res: Response,
  next: NextFunction,
) => {
  // Track validation errors
  if (error.name === "ValidationError") {
    webhookValidationErrors.labels("validation").inc();
  } else if (error.name === "SignatureError") {
    webhookValidationErrors.labels("signature").inc();
  } else {
    webhookValidationErrors.labels("unknown").inc();
  }

  next(error);
};

/**
 * Redis operation metrics helper
 */
export const trackRedisOperation = async <T>(
  operation: string,
  fn: () => Promise<T>,
): Promise<T> => {
  const startTime = Date.now();

  try {
    const result = await fn();
    const duration = (Date.now() - startTime) / 1000;

    redisOperations.labels(operation, "success").observe(duration);

    return result;
  } catch (error) {
    const duration = (Date.now() - startTime) / 1000;

    redisOperations.labels(operation, "error").observe(duration);

    throw error;
  }
};

/**
 * Get all metrics
 */
export const getMetrics = () => {
  return client.register.metrics();
};

/**
 * Reset all metrics (useful for testing)
 */
export const resetMetrics = () => {
  client.register.resetMetrics();
};
