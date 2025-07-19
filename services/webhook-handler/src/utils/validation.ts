import crypto from 'crypto';
import { logger } from './logger';

export interface WebhookPayload {
  doctype: string;
  docname: string;
  action: 'create' | 'update' | 'delete';
  data?: Record<string, any>;
  timestamp: Date;
}

export class WebhookValidator {
  private secret: string;

  constructor(secret: string) {
    this.secret = secret;
  }

  /**
   * Verify HMAC signature from Frappe webhook
   */
  verifySignature(payload: Buffer, signature: string): boolean {
    if (!signature) {
      logger.warn('Missing webhook signature');
      return false;
    }

    try {
      // Remove 'sha256=' prefix if present
      const cleanSignature = signature.replace(/^sha256=/, '');
      
      // Generate expected signature
      const expectedSignature = crypto
        .createHmac('sha256', this.secret)
        .update(payload)
        .digest('hex');

      // Use timing-safe comparison
      return crypto.timingSafeEqual(
        Buffer.from(cleanSignature, 'hex'),
        Buffer.from(expectedSignature, 'hex')
      );
    } catch (error) {
      logger.error('Signature verification failed', { error: (error as any).message });
      return false;
    }
  }

  /**
   * Validate webhook payload structure
   */
  validatePayload(payload: any): WebhookPayload {
    if (!payload || typeof payload !== 'object') {
      throw new Error('Invalid payload: must be an object');
    }

    const { doctype, name, docname, action, data } = payload;

    if (!doctype || typeof doctype !== 'string') {
      throw new Error('Invalid payload: doctype is required and must be a string');
    }

    // Accept either 'name' or 'docname' for backward compatibility
    const documentName = docname || name;
    if (!documentName || typeof documentName !== 'string') {
      throw new Error('Invalid payload: docname (or name) is required and must be a string');
    }

    if (!action || !['create', 'update', 'delete'].includes(action)) {
      throw new Error('Invalid payload: action must be create, update, or delete');
    }

    // Normalize the payload
    const normalizedPayload: WebhookPayload = {
      doctype: doctype.trim(),
      docname: documentName.trim(),
      action: action as 'create' | 'update' | 'delete',
      timestamp: new Date()
    };

    // Include data for create/update actions
    if ((action === 'create' || action === 'update') && data) {
      if (typeof data === 'object' && !Array.isArray(data)) {
        normalizedPayload.data = data;
      } else {
        logger.warn('Invalid data field in payload, ignoring', { doctype, docname: documentName });
      }
    }

    return normalizedPayload;
  }

  /**
   * Check if doctype should be processed (basic filtering)
   */
  shouldProcessDoctype(doctype: string): boolean {
    // Skip system doctypes that are typically not useful for RAG
    const skipDoctypes = [
      'User',
      'Role',
      'Permission',
      'Session',
      'Activity Log',
      'Error Log',
      'Email Queue',
      'Communication'
    ];

    return !skipDoctypes.includes(doctype);
  }
}