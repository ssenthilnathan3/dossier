import { render, screen } from '@testing-library/react';
import TypingIndicator from '../TypingIndicator';

describe('TypingIndicator', () => {
  it('renders typing indicator with correct text', () => {
    render(<TypingIndicator />);
    
    expect(screen.getByText('Thinking...')).toBeInTheDocument();
    expect(screen.getByText('Dossier')).toBeInTheDocument();
  });

  it('renders animated dots', () => {
    const { container } = render(<TypingIndicator />);
    
    const dots = container.querySelectorAll('.animate-pulse-dot');
    expect(dots).toHaveLength(3);
  });

  it('has correct structure and styling', () => {
    const { container } = render(<TypingIndicator />);
    
    // Check for avatar with gradient background
    const avatar = container.querySelector('.bg-gradient-to-br');
    expect(avatar).toBeTruthy();
    
    // Check for proper structure
    const groupContainer = container.querySelector('.group.mb-8');
    expect(groupContainer).toBeTruthy();
  });
});