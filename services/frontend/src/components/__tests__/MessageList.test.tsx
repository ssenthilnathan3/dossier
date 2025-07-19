import { render, screen } from '@testing-library/react';
import MessageList from '../MessageList';
import { Message } from '../../types/chat';

const mockMessages: Message[] = [
  {
    id: '1',
    content: 'First message',
    sender: 'user',
    timestamp: new Date('2023-01-01T12:00:00Z'),
  },
  {
    id: '2',
    content: 'Second message',
    sender: 'assistant',
    timestamp: new Date('2023-01-01T12:01:00Z'),
  },
  {
    id: '3',
    content: 'Third message',
    sender: 'user',
    timestamp: new Date('2023-01-01T12:02:00Z'),
  }
];

describe('MessageList', () => {
  it('renders all messages', () => {
    render(<MessageList messages={mockMessages} />);
    
    expect(screen.getByText('First message')).toBeInTheDocument();
    expect(screen.getByText('Second message')).toBeInTheDocument();
    expect(screen.getByText('Third message')).toBeInTheDocument();
  });

  it('renders empty list when no messages', () => {
    const { container } = render(<MessageList messages={[]} />);
    
    expect(container.firstChild?.childNodes).toHaveLength(0);
  });

  it('maintains message order', () => {
    render(<MessageList messages={mockMessages} />);
    
    const messages = screen.getAllByText(/message/);
    expect(messages[0]).toHaveTextContent('First message');
    expect(messages[1]).toHaveTextContent('Second message');
    expect(messages[2]).toHaveTextContent('Third message');
  });

  it('applies correct spacing between messages', () => {
    const { container } = render(<MessageList messages={mockMessages} />);
    
    const messageContainer = container.querySelector('.space-y-4');
    expect(messageContainer).toBeInTheDocument();
  });
});