import { render, screen } from '@testing-library/react';
import MessageBubble from '../MessageBubble';
import { Message } from '../../types/chat';

const mockUserMessage: Message = {
  id: '1',
  content: 'Hello, this is a user message',
  sender: 'user',
  timestamp: new Date('2023-01-01T12:00:00Z'),
};

const mockAssistantMessage: Message = {
  id: '2',
  content: 'Hello, this is an assistant message',
  sender: 'assistant',
  timestamp: new Date('2023-01-01T12:01:00Z'),
  sources: [
    {
      id: 'source-1',
      doctype: 'Customer',
      docname: 'CUST-001',
      fieldName: 'description',
      content: 'Sample customer description',
      metadata: {
        chunkIndex: 1,
        totalChunks: 3,
        timestamp: new Date('2023-01-01T10:00:00Z'),
        sourceUrl: '/app/customer/CUST-001'
      }
    }
  ]
};

describe('MessageBubble', () => {
  it('renders user message correctly', () => {
    render(<MessageBubble message={mockUserMessage} />);
    
    expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument();
    // Check for time display (format may vary by timezone)
    expect(screen.getByText(/\d{1,2}:\d{2}\s?(AM|PM)/)).toBeInTheDocument();
  });

  it('renders assistant message correctly', () => {
    render(<MessageBubble message={mockAssistantMessage} />);
    
    expect(screen.getByText('Hello, this is an assistant message')).toBeInTheDocument();
    // Check for time display (format may vary by timezone)
    expect(screen.getByText(/\d{1,2}:\d{2}\s?(AM|PM)/)).toBeInTheDocument();
  });

  it('displays source references for assistant messages', () => {
    render(<MessageBubble message={mockAssistantMessage} />);
    
    expect(screen.getByText('Sources (1)')).toBeInTheDocument();
    expect(screen.getByText('Customer: CUST-001')).toBeInTheDocument();
  });

  it('does not display source references for user messages', () => {
    render(<MessageBubble message={mockUserMessage} />);
    
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
  });

  it('applies correct styling for user messages', () => {
    render(<MessageBubble message={mockUserMessage} />);
    
    const messageContent = screen.getByText('Hello, this is a user message');
    const messageBubble = messageContent.closest('.bg-primary-500');
    expect(messageBubble).toHaveClass('bg-primary-500', 'text-white');
  });

  it('applies correct styling for assistant messages', () => {
    render(<MessageBubble message={mockAssistantMessage} />);
    
    const messageContent = screen.getByText('Hello, this is an assistant message');
    const messageBubble = messageContent.closest('.bg-white');
    expect(messageBubble).toHaveClass('bg-white', 'text-gray-900');
  });
});