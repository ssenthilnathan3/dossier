import { websocketService, StreamingResponse } from '../websocket';
import { io } from 'socket.io-client';

import { vi } from 'vitest';

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(),
}));

const mockIo = io as any;

describe('WebSocketService', () => {
  let mockSocket: any;

  beforeEach(() => {
    mockSocket = {
      on: vi.fn(),
      off: vi.fn(),
      emit: vi.fn(),
      disconnect: vi.fn(),
    };
    mockIo.mockReturnValue(mockSocket);
    vi.clearAllMocks();
  });

  afterEach(() => {
    websocketService.disconnect();
  });

  describe('connect', () => {
    it('connects successfully', async () => {
      const connectPromise = websocketService.connect('ws://localhost:8003');
      
      // Simulate successful connection
      const connectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'connect')[1];
      connectHandler();
      
      await expect(connectPromise).resolves.toBeUndefined();
      expect(mockIo).toHaveBeenCalledWith('ws://localhost:8003', {
        transports: ['websocket'],
        autoConnect: true,
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      });
    });

    it('handles connection errors', async () => {
      const connectPromise = websocketService.connect('ws://localhost:8003');
      
      // Simulate connection error
      const errorHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'connect_error')[1];
      const error = new Error('Connection failed');
      errorHandler(error);
      
      await expect(connectPromise).rejects.toThrow('Connection failed');
    });

    it('handles reconnection events', async () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      
      websocketService.connect('ws://localhost:8003');
      
      // Simulate reconnection
      const reconnectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'reconnect')[1];
      reconnectHandler(3);
      
      expect(consoleSpy).toHaveBeenCalledWith('WebSocket reconnected after 3 attempts');
      
      consoleSpy.mockRestore();
    });
  });

  describe('disconnect', () => {
    it('disconnects the socket', () => {
      websocketService.connect('ws://localhost:8003');
      websocketService.disconnect();
      
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('sendQuery', () => {
    beforeEach(async () => {
      const connectPromise = websocketService.connect('ws://localhost:8003');
      const connectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'connect')[1];
      connectHandler();
      await connectPromise;
    });

    it('sends query and handles streaming response', () => {
      const mockOnChunk = vi.fn();
      const query = { query: 'test query', topK: 5 };
      const messageId = 'test-message-id';

      websocketService.sendQuery(query, messageId, mockOnChunk);

      expect(mockSocket.emit).toHaveBeenCalledWith('query', {
        ...query,
        messageId,
      });

      // Simulate streaming response
      const streamHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'query_stream')[1];
      const response: StreamingResponse = {
        type: 'chunk',
        content: 'test content',
        messageId,
      };
      
      streamHandler(response);
      
      expect(mockOnChunk).toHaveBeenCalledWith(response);
    });

    it('ignores responses for different message IDs', () => {
      const mockOnChunk = vi.fn();
      const query = { query: 'test query', topK: 5 };
      const messageId = 'test-message-id';

      websocketService.sendQuery(query, messageId, mockOnChunk);

      // Simulate response for different message ID
      const streamHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'query_stream')[1];
      const response: StreamingResponse = {
        type: 'chunk',
        content: 'test content',
        messageId: 'different-message-id',
      };
      
      streamHandler(response);
      
      expect(mockOnChunk).not.toHaveBeenCalled();
    });

    it('cleans up listener on complete response', () => {
      const mockOnChunk = vi.fn();
      const query = { query: 'test query', topK: 5 };
      const messageId = 'test-message-id';

      websocketService.sendQuery(query, messageId, mockOnChunk);

      // Simulate complete response
      const streamHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'query_stream')[1];
      const response: StreamingResponse = {
        type: 'complete',
        content: 'final content',
        messageId,
      };
      
      streamHandler(response);
      
      expect(mockOnChunk).toHaveBeenCalledWith(response);
      expect(mockSocket.off).toHaveBeenCalledWith('query_stream', streamHandler);
    });

    it('handles error when not connected', () => {
      websocketService.disconnect();
      
      const mockOnChunk = vi.fn();
      const query = { query: 'test query', topK: 5 };
      const messageId = 'test-message-id';

      websocketService.sendQuery(query, messageId, mockOnChunk);

      expect(mockOnChunk).toHaveBeenCalledWith({
        type: 'error',
        error: 'WebSocket not connected',
        messageId,
      });
    });
  });

  describe('sendQueryHTTP', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('sends HTTP query successfully', async () => {
      const mockResponse = {
        answer: 'HTTP response',
        sources: [],
        confidence: 0.8,
        processingTime: 100,
      };

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const query = { query: 'test query', topK: 5 };
      const result = await websocketService.sendQueryHTTP(query);

      expect(global.fetch).toHaveBeenCalledWith('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query),
      });

      expect(result).toEqual(mockResponse);
    });

    it('handles HTTP errors', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: false,
        status: 500,
      });

      const query = { query: 'test query', topK: 5 };

      await expect(websocketService.sendQueryHTTP(query)).rejects.toThrow('HTTP error! status: 500');
    });

    it('handles network errors', async () => {
      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      const query = { query: 'test query', topK: 5 };

      await expect(websocketService.sendQueryHTTP(query)).rejects.toThrow('Network error');
    });
  });

  describe('getConnectionStatus', () => {
    it('returns false when not connected', () => {
      expect(websocketService.getConnectionStatus()).toBe(false);
    });

    it('returns true when connected', async () => {
      const connectPromise = websocketService.connect('ws://localhost:8003');
      const connectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'connect')[1];
      connectHandler();
      await connectPromise;

      expect(websocketService.getConnectionStatus()).toBe(true);
    });

    it('returns false after disconnect', async () => {
      const connectPromise = websocketService.connect('ws://localhost:8003');
      const connectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'connect')[1];
      connectHandler();
      await connectPromise;

      // Simulate disconnect
      const disconnectHandler = mockSocket.on.mock.calls.find((call: any) => call[0] === 'disconnect')[1];
      disconnectHandler();

      expect(websocketService.getConnectionStatus()).toBe(false);
    });
  });
});