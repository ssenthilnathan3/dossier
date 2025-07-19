import { io, Socket } from 'socket.io-client';
import { QueryRequest, QueryResponse } from '../types/chat';

export interface StreamingResponse {
  type: 'chunk' | 'complete' | 'error';
  content?: string;
  sources?: any[];
  error?: string;
  messageId?: string;
}

class WebSocketService {
  private socket: Socket | null = null;
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(url: string = 'ws://localhost:8003'): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.socket = io(url, {
          transports: ['websocket'],
          autoConnect: true,
          reconnection: true,
          reconnectionAttempts: this.maxReconnectAttempts,
          reconnectionDelay: this.reconnectDelay,
        });

        this.socket.on('connect', () => {
          console.log('WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          resolve();
        });

        this.socket.on('disconnect', () => {
          console.log('WebSocket disconnected');
          this.isConnected = false;
        });

        this.socket.on('connect_error', (error) => {
          console.error('WebSocket connection error:', error);
          this.isConnected = false;
          reject(error);
        });

        this.socket.on('reconnect', (attemptNumber) => {
          console.log(`WebSocket reconnected after ${attemptNumber} attempts`);
          this.isConnected = true;
          this.reconnectAttempts = 0;
        });

        this.socket.on('reconnect_error', (error) => {
          console.error('WebSocket reconnection error:', error);
          this.reconnectAttempts++;
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
    }
  }

  sendQuery(
    query: QueryRequest, 
    messageId: string,
    onChunk: (chunk: StreamingResponse) => void
  ): void {
    if (!this.socket || !this.isConnected) {
      onChunk({
        type: 'error',
        error: 'WebSocket not connected',
        messageId
      });
      return;
    }

    // Listen for streaming responses for this specific message
    const streamHandler = (response: StreamingResponse) => {
      if (response.messageId === messageId) {
        onChunk(response);
        
        // Clean up listener when complete or error
        if (response.type === 'complete' || response.type === 'error') {
          this.socket?.off('query_stream', streamHandler);
        }
      }
    };

    this.socket.on('query_stream', streamHandler);

    // Send the query with message ID
    this.socket.emit('query', {
      ...query,
      messageId
    });
  }

  getConnectionStatus(): boolean {
    return this.isConnected;
  }

  // Fallback to HTTP API when WebSocket is not available
  async sendQueryHTTP(query: QueryRequest): Promise<QueryResponse> {
    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('HTTP query error:', error);
      throw error;
    }
  }
}

export const websocketService = new WebSocketService();