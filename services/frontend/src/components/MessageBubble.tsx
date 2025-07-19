import { Message } from '../types/chat';
import { User, Sparkles } from 'lucide-react';
import SourceReferences from './SourceReferences';
import React from 'react';
interface MessageBubbleProps {
  message: Message;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.sender === 'user';
  const isAssistant = message.sender === 'assistant';

  return (
    <div className="group mb-8">
      <div className="flex items-start space-x-4">
        {/* Avatar */}
        <div className="flex-shrink-0">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isUser 
              ? 'bg-blue-600 text-white' 
              : 'bg-gradient-to-br from-purple-500 to-blue-600 text-white'
          }`}>
            {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
          </div>
        </div>

        {/* Message Content */}
        <div className="flex-1 min-w-0">
          {/* Sender Label */}
          <div className="flex items-center mb-2">
            <span className="text-sm font-medium text-gray-900">
              {isUser ? 'You' : 'Dossier'}
            </span>
            <span className="text-xs text-gray-500 ml-2">
              {message.timestamp.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
              })}
            </span>
          </div>

          {/* Message Text */}
          <div className="prose prose-sm max-w-none">
            <div className="text-gray-800 leading-relaxed whitespace-pre-wrap break-words">
              {message.content}
              {message.isStreaming && (
                <span className="inline-block w-2 h-5 bg-blue-500 ml-1 animate-pulse" />
              )}
            </div>
            {message.error && (
              <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center text-red-700 text-sm">
                  <span className="font-medium">Error:</span>
                  <span className="ml-2">{message.error}</span>
                </div>
              </div>
            )}
          </div>

          {/* Source References for Assistant Messages */}
          {isAssistant && message.sources && message.sources.length > 0 && (
            <div className="mt-4">
              <SourceReferences sources={message.sources} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;