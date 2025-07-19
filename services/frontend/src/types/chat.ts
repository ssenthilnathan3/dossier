export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
  sources?: DocumentSource[];
  isStreaming?: boolean;
  isComplete?: boolean;
  error?: string;
}

export interface DocumentSource {
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
}

export interface QueryRequest {
  query: string;
  topK?: number;
  filters?: Record<string, any>;
  includeMetadata?: boolean;
}

export interface QueryResponse {
  answer: string;
  sources: DocumentSource[];
  confidence: number;
  processingTime: number;
}