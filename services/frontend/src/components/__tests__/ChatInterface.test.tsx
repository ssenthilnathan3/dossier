import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatInterface from '../ChatInterface';
import { websocketService } from '../../services/websocket';
import { vi } from 'vitest';

// Mock the websocket service
vi.mock('../../services/websocket', () => ({
  websocketService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendQuery: vi.fn(),
    sendQueryHTTP: vi.fn(),
    getConnectionStatus: vi.fn(),
  },
}));

const mockWebsocketService = websocketService as any;

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWebsocketService.connect.mockResolvedValue();
    mockWebsocketService.getConnectionStatus.mockReturnValue(true);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it('renders the chat interface with connection status', async () => {
    render(<ChatInterface />);
    
    expect(screen.getByText('Welcome to Dossier')).toBeInTheDocument();
    expect(screen.getByText('Dossier RAG System')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });
  });

  it('shows offline status when WebSocket connection fails', async () => {
    mockWebsocketService.connect.mockRejectedValue(new Error('Connection failed'));
    
    render(<ChatInterface />);
    
    await waitFor(() => {
      expect(screen.getByText('Failed to connect to real-time service')).toBeInTheDocument();
    });
  });

  it('sends a message and handles streaming response', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    // Wait for connection
    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Message Dossier...');
    const sendButton = screen.getByLabelText('Send message');

    await user.type(input, 'Test message');
    await user.click(sendButton);

    // Check that user message appears
    expect(screen.getByText('Test message')).toBeInTheDocument();

    // Verify WebSocket sendQuery was called
    expect(mockWebsocketService.sendQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        query: 'Test message',
        topK: 5,
        includeMetadata: true,
      }),
      expect.any(String),
      expect.any(Function)
    );
  });

  it('handles streaming response chunks', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, 'Test streaming');
    await user.click(screen.getByLabelText('Send message'));

    // Get the streaming handler function
    const streamingHandler = mockWebsocketService.sendQuery.mock.calls[0][2];

    // Simulate streaming chunks
    act(() => {
      streamingHandler({
        type: 'chunk',
        content: 'This is ',
        messageId: expect.any(String),
      });
    });

    act(() => {
      streamingHandler({
        type: 'chunk',
        content: 'a streaming ',
        messageId: expect.any(String),
      });
    });

    act(() => {
      streamingHandler({
        type: 'complete',
        content: 'response.',
        sources: [
          {
            id: 'test-source',
            doctype: 'Test',
            docname: 'TEST-001',
            fieldName: 'description',
            content: 'Test content',
            metadata: {
              chunkIndex: 1,
              totalChunks: 1,
              timestamp: new Date(),
            },
          },
        ],
        messageId: expect.any(String),
      });
    });

    // Check that the complete message appears
    await waitFor(() => {
      expect(screen.getByText('This is a streaming response.')).toBeInTheDocument();
    });

    // Check that sources are displayed
    expect(screen.getByText('Sources (1)')).toBeInTheDocument();
  });

  it('falls back to HTTP when WebSocket is not connected', async () => {
    const user = userEvent.setup();
    mockWebsocketService.getConnectionStatus.mockReturnValue(false);
    mockWebsocketService.sendQueryHTTP.mockResolvedValue({
      answer: 'HTTP response',
      sources: [],
      confidence: 0.8,
      processingTime: 100,
    });

    render(<ChatInterface />);

    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, 'Test HTTP fallback');
    await user.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByText('HTTP response')).toBeInTheDocument();
    });

    expect(mockWebsocketService.sendQueryHTTP).toHaveBeenCalledWith({
      query: 'Test HTTP fallback',
      topK: 5,
      includeMetadata: true,
    });
  });

  it('handles error responses gracefully', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, 'Test error');
    await user.click(screen.getByLabelText('Send message'));

    const streamingHandler = mockWebsocketService.sendQuery.mock.calls[0][2];

    act(() => {
      streamingHandler({
        type: 'error',
        error: 'Test error message',
        messageId: expect.any(String),
      });
    });

    await waitFor(() => {
      expect(screen.getByText('Sorry, I encountered an error while processing your request.')).toBeInTheDocument();
      expect(screen.getByText('Error:')).toBeInTheDocument();
      expect(screen.getByText('Test error message')).toBeInTheDocument();
    });
  });

  it('shows typing indicator during streaming', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, 'Test typing');
    await user.click(screen.getByLabelText('Send message'));

    // Should show typing indicator
    expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();

    // Complete the streaming
    const streamingHandler = mockWebsocketService.sendQuery.mock.calls[0][2];
    act(() => {
      streamingHandler({
        type: 'complete',
        content: 'Done',
        messageId: expect.any(String),
      });
    });

    // Typing indicator should disappear
    await waitFor(() => {
      expect(screen.queryByTestId('typing-indicator')).not.toBeInTheDocument();
    });
  });

  it('handles suggestion clicks', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByText('Real-time connected')).toBeInTheDocument();
    });

    const suggestion = screen.getByText('What customers do we have?');
    await user.click(suggestion);

    expect(screen.getByText('What customers do we have?')).toBeInTheDocument();
    expect(mockWebsocketService.sendQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        query: 'What customers do we have?',
      }),
      expect.any(String),
      expect.any(Function)
    );
  });

  it('is mobile responsive', () => {
    // Mock mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 375,
    });

    render(<ChatInterface />);

    // Check that mobile-specific classes are applied
    const connectionStatus = screen.getByText('Connected');
    expect(connectionStatus).toBeInTheDocument();

    // Check that desktop-only elements are hidden
    expect(screen.queryByText('Real-time connected')).not.toBeInTheDocument();
  });

  it('disconnects WebSocket on unmount', () => {
    const { unmount } = render(<ChatInterface />);
    
    unmount();
    
    expect(mockWebsocketService.disconnect).toHaveBeenCalled();
  });
});