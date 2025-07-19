interface LogLevel {
  ERROR: 'error';
  WARN: 'warn';
  INFO: 'info';
  DEBUG: 'debug';
}

const LOG_LEVELS: LogLevel = {
  ERROR: 'error',
  WARN: 'warn',
  INFO: 'info',
  DEBUG: 'debug'
};

interface LogEntry {
  timestamp: string;
  level: string;
  service: string;
  version: string;
  message: string;
  correlation_id?: string;
  request_id?: string;
  trace_id?: string;
  user_id?: string;
  operation?: string;
  duration?: number;
  error?: {
    type: string;
    message: string;
    stack?: string;
  };
  [key: string]: any;
}

class Logger {
  private context: Record<string, any> = {};
  
  setContext(context: Record<string, any>) {
    this.context = { ...this.context, ...context };
  }
  
  clearContext() {
    this.context = {};
  }
  
  private shouldLog(level: string): boolean {
    const logLevel = process.env.LOG_LEVEL || 'info';
    const levels = ['debug', 'info', 'warn', 'error'];
    const currentLevelIndex = levels.indexOf(logLevel);
    const messageLevelIndex = levels.indexOf(level);
    
    return messageLevelIndex >= currentLevelIndex;
  }
  
  private log(level: string, message: string, meta?: any) {
    if (!this.shouldLog(level)) {
      return;
    }
    
    const timestamp = new Date().toISOString();
    const logEntry: LogEntry = {
      timestamp,
      level,
      service: 'webhook-handler',
      version: '1.0.0',
      message,
      ...this.context,
      ...(meta && meta)
    };
    
    // Handle error objects
    if (meta?.error && meta.error instanceof Error) {
      logEntry.error = {
        type: meta.error.constructor.name,
        message: meta.error.message,
        stack: meta.error.stack
      };
      // Remove the original error object from meta to avoid circular references
      const { error, ...restMeta } = meta;
      Object.assign(logEntry, restMeta);
    }
    
    console.log(JSON.stringify(logEntry));
  }

  error(message: string, meta?: any) {
    this.log(LOG_LEVELS.ERROR, message, meta);
  }

  warn(message: string, meta?: any) {
    this.log(LOG_LEVELS.WARN, message, meta);
  }

  info(message: string, meta?: any) {
    this.log(LOG_LEVELS.INFO, message, meta);
  }

  debug(message: string, meta?: any) {
    this.log(LOG_LEVELS.DEBUG, message, meta);
  }
  
  // Convenience method for timing operations
  time(operation: string): () => void {
    const startTime = Date.now();
    return () => {
      const duration = Date.now() - startTime;
      this.info(`Operation completed: ${operation}`, { operation, duration });
    };
  }
  
  // Method for logging with correlation tracking
  withCorrelation(correlationId: string, fn: () => void) {
    const originalContext = { ...this.context };
    this.setContext({ correlation_id: correlationId });
    
    try {
      fn();
    } finally {
      this.context = originalContext;
    }
  }
}

export const logger = new Logger();