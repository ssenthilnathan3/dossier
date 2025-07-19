import React, { useState } from 'react';
import { DocumentSource } from '../types/chat';
import { ChevronDown, ChevronRight, ExternalLink, FileText, Link, Copy, Check } from 'lucide-react';

interface SourceReferencesProps {
  sources: DocumentSource[];
}

const SourceReferences: React.FC<SourceReferencesProps> = ({ sources }) => {
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [copiedSources, setCopiedSources] = useState<Set<string>>(new Set());

  const toggleSource = (sourceId: string) => {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(sourceId)) {
      newExpanded.delete(sourceId);
    } else {
      newExpanded.add(sourceId);
    }
    setExpandedSources(newExpanded);
  };

  const copySourceContent = async (source: DocumentSource) => {
    try {
      await navigator.clipboard.writeText(source.content);
      setCopiedSources(prev => new Set(prev).add(source.id));
      setTimeout(() => {
        setCopiedSources(prev => {
          const newSet = new Set(prev);
          newSet.delete(source.id);
          return newSet;
        });
      }, 2000);
    } catch (error) {
      console.error('Failed to copy content:', error);
    }
  };

  const highlightText = (text: string, searchTerms: string[] = []) => {
    if (!searchTerms.length) return text;
    
    const regex = new RegExp(`(${searchTerms.join('|')})`, 'gi');
    const parts = text.split(regex);
    
    return parts.map((part, index) => {
      if (searchTerms.some(term => part.toLowerCase().includes(term.toLowerCase()))) {
        return (
          <mark key={index} className="bg-yellow-200 px-1 rounded">
            {part}
          </mark>
        );
      }
      return part;
    });
  };

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-200">
      <div className="flex items-center mb-3">
        <Link className="w-4 h-4 text-blue-600 mr-2" />
        <span className="text-sm font-semibold text-gray-800">
          Sources ({sources.length})
        </span>
      </div>
      
      <div className="space-y-2">
        {sources.map((source, index) => {
          const isExpanded = expandedSources.has(source.id);
          
          return (
            <div key={source.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-sm transition-shadow">
              {/* Source Header */}
              <button
                onClick={() => toggleSource(source.id)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-600 rounded-full text-xs font-medium">
                      {index + 1}
                    </span>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {source.doctype}: {source.docname}
                      </span>
                    </div>
                    <div className="flex items-center mt-1">
                      <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                        {source.fieldName}
                      </span>
                    </div>
                  </div>
                </div>
                
                {source.metadata.sourceUrl && (
                  <ExternalLink 
                    data-testid="external-link"
                    className="w-4 h-4 text-gray-400 hover:text-blue-600 flex-shrink-0 ml-2" 
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(source.metadata.sourceUrl, '_blank');
                    }}
                  />
                )}
              </button>

              {/* Expanded Content */}
              {isExpanded && (
                <div className="px-4 pb-4 border-t border-gray-100">
                  <div className="mt-3 relative">
                    <div className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg leading-relaxed border-l-4 border-blue-200">
                      <div className="whitespace-pre-wrap break-words">
                        {highlightText(source.content)}
                      </div>
                    </div>
                    
                    {/* Copy Button */}
                    <button
                      onClick={() => copySourceContent(source)}
                      className="absolute top-2 right-2 p-1.5 bg-white rounded-md shadow-sm border border-gray-200 hover:bg-gray-50 transition-colors"
                      title="Copy content"
                    >
                      {copiedSources.has(source.id) ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <Copy className="w-3 h-3 text-gray-500" />
                      )}
                    </button>
                  </div>
                  
                  <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-gray-500">
                    <div className="flex items-center space-x-4">
                      <span className="flex items-center space-x-1">
                        <span>Chunk {source.metadata.chunkIndex} of {source.metadata.totalChunks}</span>
                      </span>
                      <span className="hidden sm:inline">•</span>
                      <span>
                        {source.metadata.timestamp.toLocaleDateString()}
                      </span>
                    </div>
                    
                    {source.metadata.sourceUrl && (
                      <button
                        onClick={() => window.open(source.metadata.sourceUrl, '_blank')}
                        className="flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>View Document</span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SourceReferences;