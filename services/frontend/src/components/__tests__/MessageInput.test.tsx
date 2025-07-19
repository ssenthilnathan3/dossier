import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import MessageInput from '../MessageInput';

describe('MessageInput', () => {
  const mockOnChange = vi.fn();
  const mockOnSend = vi.fn();

  beforeEach(() => {
    mockOnChange.mockClear();
    mockOnSend.mockClear();
  });

  it('renders input field with placeholder', () => {
    render(
      <MessageInput
        value=""
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    expect(screen.getByPlaceholderText('Message Dossier...')).toBeInTheDocument();
  });

  it('calls onChange when typing', async () => {
    const user = userEvent.setup();
    
    render(
      <MessageInput
        value=""
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, 'Hello');
    
    expect(mockOnChange).toHaveBeenCalledWith('H');
  });

  it('calls onSend when form is submitted', async () => {
    const user = userEvent.setup();
    
    render(
      <MessageInput
        value="Test message"
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const button = screen.getByRole('button', { name: /send message/i });
    await user.click(button);
    
    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  it('calls onSend when Enter is pressed', async () => {
    const user = userEvent.setup();
    
    render(
      <MessageInput
        value="Test message"
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const input = screen.getByPlaceholderText('Message Dossier...');
    await user.type(input, '{enter}');
    
    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  it('does not call onSend when Shift+Enter is pressed', () => {
    render(
      <MessageInput
        value="Test message"
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const input = screen.getByPlaceholderText('Message Dossier...');
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    
    expect(mockOnSend).not.toHaveBeenCalled();
  });

  it('disables input and button when disabled prop is true', () => {
    render(
      <MessageInput
        value="Test message"
        onChange={mockOnChange}
        onSend={mockOnSend}
        disabled={true}
      />
    );
    
    const input = screen.getByPlaceholderText('Message Dossier...');
    const button = screen.getByRole('button', { name: /send message/i });
    
    expect(input).toBeDisabled();
    expect(button).toBeDisabled();
  });

  it('disables button when input is empty', () => {
    render(
      <MessageInput
        value=""
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const button = screen.getByRole('button', { name: /send message/i });
    expect(button).toBeDisabled();
  });

  it('disables button when input contains only whitespace', () => {
    render(
      <MessageInput
        value="   "
        onChange={mockOnChange}
        onSend={mockOnSend}
      />
    );
    
    const button = screen.getByRole('button', { name: /send message/i });
    expect(button).toBeDisabled();
  });


});