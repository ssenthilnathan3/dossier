/**
 * Shared TypeScript interfaces for Dossier RAG System
 * These interfaces define the core data models used across all services
 */

export interface DoctypeConfig {
  doctype: string;
  enabled: boolean;
  fields: string[];
  filters: Record<string, any>;
  chunkSize: number;
  chunkOverlap: number;
  lastSync?: Date;
}

export interface DocumentChunk {
  id: string;
  doctype: string;
  docname: string;
  fieldName: string;
  content: string;
  metadata: {
    chunkIndex: number;
    totalChunks: number;
    timestamp: Date;
    sourceUrl?: string;
  };
  embedding?: number[];
}

export interface QueryRequest {
  query: string;
  topK?: number;
  filters?: Record<string, any>;
  includeMetadata?: boolean;
}

export interface QueryResponse {
  answer: string;
  sources: DocumentChunk[];
  confidence: number;
  processingTime: number;
}

export interface WebhookPayload {
  doctype: string;
  docname: string;
  action: 'create' | 'update' | 'delete';
  data?: Record<string, any>;
  timestamp: Date;
}

export interface IngestionRequest {
  doctype: string;
  filters?: Record<string, any>;
  batchSize?: number;
  forceUpdate?: boolean;
}

export interface IngestionResponse {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  processed: number;
  updated: number;
  failed: number;
  errors?: string[];
}