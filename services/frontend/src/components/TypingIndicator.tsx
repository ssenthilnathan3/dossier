import React from 'react';
import { Sparkles } from 'lucide-react';

const TypingIndicator: React.FC = () => {
  return (
    <div className="group mb-8">
      <div className="flex items-start space-x-4">
        {/* Avatar */}
        <div className="flex-shrink-0">
          <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gradient-to-br from-purple-500 to-blue-600 text-white">
            <Sparkles className="w-4 h-4" />
          </div>
        </div>

        {/* Typing Content */}
        <div className="flex-1 min-w-0">
          {/* Sender Label */}
          <div className="flex items-center mb-2">
            <span className="text-sm font-medium text-gray-900">Dossier</span>
          </div>

          {/* Typing Animation */}
          <div className="flex items-center space-x-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse-dot"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse-dot" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse-dot" style={{ animationDelay: '0.4s' }}></div>
            </div>
            <span className="text-sm text-gray-500">Thinking...</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;