import crypto from 'crypto';
import { WebhookValidator } from '../utils/validation';
import { it } from 'node:test';
import { beforeEach } from 'node:test';
import { describe } from 'node:test';

describe('WebhookValidator', () => {
  const testSecret = 'test-webhook-secret';
  let validator: WebhookValidator;

  beforeEach(() => {
    validator = new WebhookValidator(testSecret);
  });

  describe('verifySignature', () => {
    it('should verify valid HMAC signature', () => {
      const payload = Buffer.from(JSON.stringify({ test: 'data' }));
      const signature = crypto
        .createHmac('sha256', testSecret)
        .update(payload)
        .digest('hex');

      expect(validator.verifySignature(payload, `sha256=${signature}`)).toBe(true);
    });

    it('should verify valid signature without sha256 prefix', () => {
      const payload = Buffer.from(JSON.stringify({ test: 'data' }));
      const signature = crypto
        .createHmac('sha256', testSecret)
        .update(payload)
        .digest('hex');

      expect(validator.verifySignature(payload, signature)).toBe(true);
    });

    it('should reject invalid signature', () => {
      const payload = Buffer.from(JSON.stringify({ test: 'data' }));
      const invalidSignature = 'invalid-signature';

      expect(validator.verifySignature(payload, invalidSignature)).toBe(false);
    });

    it('should reject missing signature', () => {
      const payload = Buffer.from(JSON.stringify({ test: 'data' }));

      expect(validator.verifySignature(payload, '')).toBe(false);
    });

    it('should handle signature verification errors gracefully', () => {
      const payload = Buffer.from(JSON.stringify({ test: 'data' }));
      const malformedSignature = 'sha256=not-hex';

      expect(validator.verifySignature(payload, malformedSignature)).toBe(false);
    });
  });

  describe('validatePayload', () => {
    it('should validate correct payload structure', () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create',
        data: { customer_name: 'Test Customer' }
      };

      const result = validator.validatePayload(payload);

      expect(result).toEqual({
        doctype: 'Customer',
        docname: 'CUST-001',
        action: 'create',
        data: { customer_name: 'Test Customer' },
        timestamp: expect.any(Date)
      });
    });

    it('should validate payload without data field', () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'delete'
      };

      const result = validator.validatePayload(payload);

      expect(result).toEqual({
        doctype: 'Customer',
        docname: 'CUST-001',
        action: 'delete',
        timestamp: expect.any(Date)
      });
    });

    it('should trim whitespace from doctype and name', () => {
      const payload = {
        doctype: '  Customer  ',
        name: '  CUST-001  ',
        action: 'update'
      };

      const result = validator.validatePayload(payload);

      expect(result.doctype).toBe('Customer');
      expect(result.docname).toBe('CUST-001');
    });

    it('should throw error for missing doctype', () => {
      const payload = {
        name: 'CUST-001',
        action: 'create'
      };

      expect(() => validator.validatePayload(payload)).toThrow(
        'Invalid payload: doctype is required and must be a string'
      );
    });

    it('should throw error for missing name', () => {
      const payload = {
        doctype: 'Customer',
        action: 'create'
      };

      expect(() => validator.validatePayload(payload)).toThrow(
        'Invalid payload: docname (or name) is required and must be a string'
      );
    });

    it('should throw error for invalid action', () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'invalid-action'
      };

      expect(() => validator.validatePayload(payload)).toThrow(
        'Invalid payload: action must be create, update, or delete'
      );
    });

    it('should throw error for non-object payload', () => {
      expect(() => validator.validatePayload('invalid')).toThrow(
        'Invalid payload: must be an object'
      );
    });

    it('should throw error for null payload', () => {
      expect(() => validator.validatePayload(null)).toThrow(
        'Invalid payload: must be an object'
      );
    });

    it('should handle invalid data field gracefully', () => {
      const payload = {
        doctype: 'Customer',
        name: 'CUST-001',
        action: 'create',
        data: 'invalid-data-type'
      };

      const result = validator.validatePayload(payload);

      expect(result.data).toBeUndefined();
    });
  });

  describe('shouldProcessDoctype', () => {
    it('should process regular business doctypes', () => {
      expect(validator.shouldProcessDoctype('Customer')).toBe(true);
      expect(validator.shouldProcessDoctype('Sales Order')).toBe(true);
      expect(validator.shouldProcessDoctype('Item')).toBe(true);
    });

    it('should skip system doctypes', () => {
      expect(validator.shouldProcessDoctype('User')).toBe(false);
      expect(validator.shouldProcessDoctype('Role')).toBe(false);
      expect(validator.shouldProcessDoctype('Session')).toBe(false);
      expect(validator.shouldProcessDoctype('Error Log')).toBe(false);
    });
  });
});