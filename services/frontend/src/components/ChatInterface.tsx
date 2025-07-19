import React, { useState, useRef, useEffect } from 'react';
import { Message, QueryRequest } from '../types/chat';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import TypingIndicator from './TypingIndicator';
import { MessageSquare, Sparkles, Wifi, WifiOff } from 'lucide-react';
import { websocketService, StreamingResponse } from '../services/websocket';

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize WebSocket connection
  useEffect(() => {
    const initializeWebSocket = async () => {
      try {
        await websocketService.connect();
        setIsConnected(true);
        setConnectionError(null);
      } catch (error) {
        console.error('Failed to connect to WebSocket:', error);
        setIsConnected(false);
        setConnectionError('Failed to connect to real-time service');
      }
    };

    initializeWebSocket();

    return () => {
      websocketService.disconnect();
    };
  }, []);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content: content.trim(),
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    // Create assistant message placeholder for streaming
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      content: '',
      sender: 'assistant',
      timestamp: new Date(),
      isStreaming: true,
      isComplete: false,
    };

    setMessages(prev => [...prev, assistantMessage]);

    const query: QueryRequest = {
      query: content.trim(),
      topK: 5,
      includeMetadata: true,
    };

    // Handle streaming response
    const handleStreamingChunk = (chunk: StreamingResponse) => {
      setMessages(prev => prev.map(msg => {
        if (msg.id === assistantMessageId) {
          switch (chunk.type) {
            case 'chunk':
              return {
                ...msg,
                content: msg.content + (chunk.content || ''),
                isStreaming: true,
              };
            case 'complete':
              return {
                ...msg,
                content: msg.content + (chunk.content || ''),
                sources: chunk.sources || [],
                isStreaming: false,
                isComplete: true,
              };
            case 'error':
              return {
                ...msg,
                content: 'Sorry, I encountered an error while processing your request.',
                error: chunk.error,
                isStreaming: false,
                isComplete: true,
              };
            default:
              return msg;
          }
        }
        return msg;
      }));

      if (chunk.type === 'complete' || chunk.type === 'error') {
        setIsTyping(false);
      }
    };

    // Try WebSocket first, fallback to HTTP
    if (isConnected) {
      websocketService.sendQuery(query, assistantMessageId, handleStreamingChunk);
    } else {
      // Fallback to HTTP API
      try {
        const response = await websocketService.sendQueryHTTP(query);
        setMessages(prev => prev.map(msg => {
          if (msg.id === assistantMessageId) {
            return {
              ...msg,
              content: response.answer,
              sources: response.sources,
              isStreaming: false,
              isComplete: true,
            };
          }
          return msg;
        }));
      } catch (error) {
        setMessages(prev => prev.map(msg => {
          if (msg.id === assistantMessageId) {
            return {
              ...msg,
              content: 'Sorry, I encountered an error while processing your request.',
              error: error instanceof Error ? error.message : 'Unknown error',
              isStreaming: false,
              isComplete: true,
            };
          }
          return msg;
        }));
      } finally {
        setIsTyping(false);
      }
    }
  };

  const EmptyState = () => (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
        <Sparkles className="w-8 h-8 text-white" />
      </div>
      <h2 className="text-2xl font-semibold text-gray-800 mb-3">
        Welcome to Dossier
      </h2>
      <p className="text-gray-600 mb-8 max-w-md">
        Your AI assistant for Frappe documents. Ask me anything about your data and I'll help you find the information you need.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
        {[
          "What customers do we have?",
          "Show me recent sales orders",
          "Find items with low stock",
          "Summarize this month's revenue"
        ].map((suggestion, index) => (
          <button
            key={index}
            onClick={() => handleSendMessage(suggestion)}
            className="p-4 text-left bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-sm transition-all duration-200 group"
          >
            <div className="flex items-center">
              <MessageSquare className="w-4 h-4 text-gray-400 mr-3 group-hover:text-blue-500" />
              <span className="text-gray-700 group-hover:text-gray-900">{suggestion}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Connection Status Bar */}
      <div className="bg-white border-b border-gray-200 px-3 sm:px-4 py-2">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-2">
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-500" />
                  <span className="text-xs sm:text-sm text-green-600 font-medium">
                    <span className="hidden sm:inline">Real-time connected</span>
                    <span className="sm:hidden">Connected</span>
                  </span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-orange-500" />
                  <span className="text-xs sm:text-sm text-orange-600 font-medium">
                    <span className="hidden sm:inline">{connectionError || 'Connecting...'}</span>
                    <span className="sm:hidden">Offline</span>
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="text-xs text-gray-500 hidden sm:block">
            Dossier RAG System
          </div>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-hidden">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="h-full overflow-y-auto">
            <div className="max-w-4xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
              <MessageList messages={messages} />
              {isTyping && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <MessageInput
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSendMessage}
            disabled={isTyping}
          />
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;