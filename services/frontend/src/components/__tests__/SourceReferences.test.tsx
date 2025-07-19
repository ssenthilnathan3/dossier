import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SourceReferences from '../SourceReferences';
import { DocumentSource } from '../../types/chat';
import { vi } from 'vitest';

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn(),
  },
});

const mockSources: DocumentSource[] = [
  {
    id: 'source-1',
    doctype: 'Customer',
    docname: 'CUST-001',
    fieldName: 'description',
    content: 'Sample customer description content',
    metadata: {
      chunkIndex: 1,
      totalChunks: 3,
      timestamp: new Date('2023-01-01T10:00:00Z'),
      sourceUrl: '/app/customer/CUST-001'
    }
  },
  {
    id: 'source-2',
    doctype: 'Item',
    docname: 'ITEM-001',
    fieldName: 'item_name',
    content: 'Sample item name content',
    metadata: {
      chunkIndex: 2,
      totalChunks: 5,
      timestamp: new Date('2023-01-01T11:00:00Z'),
    }
  }
];

describe('SourceReferences', () => {
  it('renders source count correctly', () => {
    render(<SourceReferences sources={mockSources} />);
    
    expect(screen.getByText('Sources (2)')).toBeInTheDocument();
  });

  it('renders source headers', () => {
    render(<SourceReferences sources={mockSources} />);
    
    expect(screen.getByText('Customer: CUST-001')).toBeInTheDocument();
    expect(screen.getByText('Item: ITEM-001')).toBeInTheDocument();
  });

  it('shows field names as badges', () => {
    render(<SourceReferences sources={mockSources} />);
    
    expect(screen.getByText('description')).toBeInTheDocument();
    expect(screen.getByText('item_name')).toBeInTheDocument();
  });

  it('expands source content when clicked', async () => {
    const user = userEvent.setup();
    render(<SourceReferences sources={mockSources} />);
    
    const sourceButton = screen.getByText('Customer: CUST-001').closest('button');
    expect(sourceButton).toBeInTheDocument();
    
    await user.click(sourceButton!);
    
    expect(screen.getByText('Sample customer description content')).toBeInTheDocument();
    expect(screen.getByText('Chunk 1 of 3')).toBeInTheDocument();
  });

  it('collapses source content when clicked again', async () => {
    const user = userEvent.setup();
    render(<SourceReferences sources={mockSources} />);
    
    const sourceButton = screen.getByText('Customer: CUST-001').closest('button');
    expect(sourceButton).toBeInTheDocument();
    
    // Expand
    await user.click(sourceButton!);
    expect(screen.getByText('Sample customer description content')).toBeInTheDocument();
    
    // Collapse
    await user.click(sourceButton!);
    expect(screen.queryByText('Sample customer description content')).not.toBeInTheDocument();
  });

  it('shows external link for sources with sourceUrl', () => {
    render(<SourceReferences sources={mockSources} />);
    
    const externalLinks = screen.getAllByTestId('external-link');
    expect(externalLinks).toHaveLength(1); // Only first source has sourceUrl
  });

  it('does not render when sources array is empty', () => {
    const { container } = render(<SourceReferences sources={[]} />);
    
    expect(container.firstChild).toBeNull();
  });

  it('does not render when sources is undefined', () => {
    const { container } = render(<SourceReferences sources={undefined as any} />);
    
    expect(container.firstChild).toBeNull();
  });

  it('shows correct timestamp format', async () => {
    const user = userEvent.setup();
    render(<SourceReferences sources={mockSources} />);
    
    const sourceButton = screen.getByText('Customer: CUST-001').closest('button');
    await user.click(sourceButton!);
    
    expect(screen.getByText('1/1/2023')).toBeInTheDocument();
  });

  it('copies source content to clipboard', async () => {
    const user = userEvent.setup();
    const writeTextSpy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    
    render(<SourceReferences sources={mockSources} />);
    
    // Expand first source
    const firstSourceButton = screen.getByText('Customer: CUST-001').closest('button');
    await user.click(firstSourceButton!);
    
    // Click copy button
    const copyButton = screen.getByTitle('Copy content');
    await user.click(copyButton);
    
    expect(writeTextSpy).toHaveBeenCalledWith('Sample customer description content');
    
    writeTextSpy.mockRestore();
  });

  it('shows check icon after successful copy', async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    
    render(<SourceReferences sources={mockSources} />);
    
    // Expand first source
    const firstSourceButton = screen.getByText('Customer: CUST-001').closest('button');
    await user.click(firstSourceButton!);
    
    // Click copy button
    const copyButton = screen.getByTitle('Copy content');
    await user.click(copyButton);
    
    // Should show check icon briefly
    await waitFor(() => {
      expect(copyButton.querySelector('svg')).toBeInTheDocument();
    });
  });

  it('opens external link in new tab', async () => {
    const user = userEvent.setup();
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    
    render(<SourceReferences sources={mockSources} />);
    
    const externalLink = screen.getByTestId('external-link');
    await user.click(externalLink);
    
    expect(windowOpenSpy).toHaveBeenCalledWith('/app/customer/CUST-001', '_blank');
    
    windowOpenSpy.mockRestore();
  });

  it('shows View Document button when sourceUrl is available', async () => {
    const user = userEvent.setup();
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    
    render(<SourceReferences sources={mockSources} />);
    
    // Expand first source (has sourceUrl)
    const firstSourceButton = screen.getByText('Customer: CUST-001').closest('button');
    await user.click(firstSourceButton!);
    
    const viewDocButton = screen.getByText('View Document');
    await user.click(viewDocButton);
    
    expect(windowOpenSpy).toHaveBeenCalledWith('/app/customer/CUST-001', '_blank');
    
    windowOpenSpy.mockRestore();
  });

  it('does not show View Document button when sourceUrl is not available', async () => {
    const user = userEvent.setup();
    render(<SourceReferences sources={mockSources} />);
    
    // Expand second source (no sourceUrl)
    const secondSourceButton = screen.getByText('Item: ITEM-001').closest('button');
    await user.click(secondSourceButton!);
    
    expect(screen.queryByText('View Document')).not.toBeInTheDocument();
  });

  it('handles copy failure gracefully', async () => {
    const user = userEvent.setup();
    const writeTextSpy = vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('Copy failed'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    
    render(<SourceReferences sources={mockSources} />);
    
    // Expand first source
    const firstSourceButton = screen.getByText('Customer: CUST-001').closest('button');
    await user.click(firstSourceButton!);
    
    // Click copy button
    const copyButton = screen.getByTitle('Copy content');
    await user.click(copyButton);
    
    expect(writeTextSpy).toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalledWith('Failed to copy content:', expect.any(Error));
    
    writeTextSpy.mockRestore();
    consoleSpy.mockRestore();
  });

  it('is mobile responsive with proper layout', () => {
    render(<SourceReferences sources={mockSources} />);
    
    // Check that the component renders without issues
    expect(screen.getByText('Sources (2)')).toBeInTheDocument();
    
    // The responsive design should handle the layout properly
    const sourceContainer = screen.getByText('Sources (2)').closest('div');
    expect(sourceContainer).toHaveClass('flex', 'items-center', 'mb-3');
  });
});