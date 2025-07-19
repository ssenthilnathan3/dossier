import React, { useRef, useEffect } from 'react';
import { Send, Paperclip } from 'lucide-react';

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (message: string) => void;
  disabled?: boolean;
}

const MessageInput: React.FC<MessageInputProps> = ({
  value,
  onChange,
  onSend,
  disabled = false
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) {
        onSend(value);
      }
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  return (
    <div className="relative">
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex items-end bg-white border border-gray-300 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-200 focus-within:border-blue-500 focus-within:shadow-md">
          {/* Attachment button */}
          <button
            type="button"
            className="p-3 text-gray-400 hover:text-gray-600 transition-colors"
            disabled={disabled}
          >
            <Paperclip className="w-5 h-5" />
          </button>
          
          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Dossier..."
            disabled={disabled}
            className={`flex-1 px-2 py-3 bg-transparent border-none resize-none focus:outline-none placeholder-gray-500 ${
              disabled ? 'cursor-not-allowed' : ''
            }`}
            rows={1}
            style={{ minHeight: '24px', maxHeight: '120px' }}
          />
          
          {/* Send button */}
          <button
            type="submit"
            disabled={!value.trim() || disabled}
            aria-label="Send message"
            className={`p-2 m-2 rounded-full transition-all duration-200 ${
              !value.trim() || disabled
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow-md'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
      
      {/* Helper text */}
      <div className="flex items-center justify-center mt-2 text-xs text-gray-500">
        <span>Dossier can make mistakes. Consider checking important information.</span>
      </div>
    </div>
  );
};

export default MessageInput;