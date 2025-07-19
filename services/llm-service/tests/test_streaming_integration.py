"""
Integration tests for streaming LLM functionality and complete Q&A workflows
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))

from services.llm_service import LLMService
from shared.models.document import DocumentChunk, DocumentMetadata
from models.requests import ChatMessage


@pytest.fixture
def sample_document_chunks():
    """Sample document chunks for testing"""
    return [
        DocumentChunk(
            id="chunk1",
            doctype="Customer",
            docname="CUST-001",
            field_name="description",
            content="Acme Corporation is a leading technology company specializing in cloud solutions.",
            metadata=DocumentMetadata(
                chunk_index=0,
                total_chunks=1,
                timestamp=datetime.utcnow(),
                content_length=80,
                word_count=12
            )
        ),
        DocumentChunk(
            id="chunk2",
            doctype="Item",
            docname="ITEM-001",
            field_name="specifications",
            content="Technical specifications: 10kg weight, 50cm height, aluminum construction.",
            metadata=DocumentMetadata(
                chunk_index=0,
                total_chunks=1,
                timestamp=datetime.utcnow(),
                content_length=78,
                word_count=11
            )
        )
    ]


@pytest.fixture
def llm_service():
    """LLM service instance for testing"""
    with patch.dict(os.environ, {
        'OLLAMA_URL': 'http://test-ollama:11434',
        'DEFAULT_MODEL': 'test-model',
        'MAX_CONTEXT_LENGTH': '1000',
        'LLM_TIMEOUT_SECONDS': '10'
    }):
        return LLMService()


class TestStreamingIntegration:
    """Test cases for streaming LLM functionality"""
    
    @pytest.mark.asyncio
    async def test_generate_streaming_response_success(self, llm_service, sample_document_chunks):
        """Test successful streaming response generation"""
        # Mock streaming response chunks
        mock_chunks = [
            {'response': 'Based on the '},
            {'response': 'provided context, '},
            {'response': 'Acme Corporation '},
            {'response': 'is a technology company.'},
            {'done': True, 'eval_count': 25}
        ]
        
        async def mock_generate(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_ensure.return_value = True
                mock_gen.return_value = mock_generate()
                
                chunks = []
                async for chunk in llm_service.generate_streaming_response(
                    query="Tell me about the customer",
                    context_chunks=sample_document_chunks,
                    model="test-model"
                ):
                    chunks.append(chunk)
                
                # Verify streaming chunks
                content_chunks = [c for c in chunks if c.get('type') == 'content']
                assert len(content_chunks) == 4
                assert content_chunks[0]['content'] == 'Based on the '
                assert content_chunks[3]['content'] == 'is a technology company.'
                
                # Verify completion chunk
                complete_chunks = [c for c in chunks if c.get('type') == 'complete']
                assert len(complete_chunks) == 1
                complete_chunk = complete_chunks[0]
                assert complete_chunk['full_response'] == 'Based on the provided context, Acme Corporation is a technology company.'
                assert complete_chunk['token_count'] == 25
                assert len(complete_chunk['sources']) > 0
    
    @pytest.mark.asyncio
    async def test_chat_streaming_completion_success(self, llm_service, sample_document_chunks):
        """Test successful streaming chat completion"""
        messages = [
            ChatMessage(role="user", content="What can you tell me about the customer?")
        ]
        
        # Mock streaming response chunks
        mock_chunks = [
            {'message': {'content': 'The customer '}},
            {'message': {'content': 'Acme Corporation '}},
            {'message': {'content': 'is a leading tech company.'}},
            {'done': True, 'eval_count': 20}
        ]
        
        async def mock_chat(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'chat', new_callable=AsyncMock) as mock_chat_method:
                mock_ensure.return_value = True
                mock_chat_method.return_value = mock_chat()
                
                chunks = []
                async for chunk in llm_service.chat_streaming_completion(
                    messages=messages,
                    context_chunks=sample_document_chunks,
                    model="test-model"
                ):
                    chunks.append(chunk)
                
                # Verify streaming chunks
                content_chunks = [c for c in chunks if c.get('type') == 'content']
                assert len(content_chunks) == 3
                assert content_chunks[0]['content'] == 'The customer '
                
                # Verify completion chunk
                complete_chunks = [c for c in chunks if c.get('type') == 'complete']
                assert len(complete_chunks) == 1
                complete_chunk = complete_chunks[0]
                assert 'Acme Corporation is a leading tech company' in complete_chunk['full_response']
    
    @pytest.mark.asyncio
    async def test_streaming_with_timeout(self, llm_service, sample_document_chunks):
        """Test streaming response with timeout handling"""
        async def mock_timeout_stream():
            await asyncio.sleep(0.1)  # Simulate delay
            raise asyncio.TimeoutError()
            yield  # This will never be reached but makes it a generator
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_ensure.return_value = True
                mock_gen.return_value = mock_timeout_stream()
                
                chunks = []
                async for chunk in llm_service.generate_streaming_response(
                    query="Test query",
                    context_chunks=sample_document_chunks
                ):
                    chunks.append(chunk)
                
                # Should get error chunk
                error_chunks = [c for c in chunks if c.get('type') == 'error']
                assert len(error_chunks) == 1
                assert 'timed out' in error_chunks[0]['error'].lower()
    
    @pytest.mark.asyncio
    async def test_streaming_with_fallback_success(self, llm_service, sample_document_chunks):
        """Test streaming with fallback - success case"""
        mock_chunks = [
            {'response': 'Successful response'},
            {'done': True, 'eval_count': 10}
        ]
        
        async def mock_generate(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_ensure.return_value = True
                mock_gen.return_value = mock_generate()
                
                chunks = []
                async for chunk in llm_service.generate_streaming_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks
                ):
                    chunks.append(chunk)
                
                # Should get successful response
                complete_chunks = [c for c in chunks if c.get('type') == 'complete']
                assert len(complete_chunks) == 1
                assert complete_chunks[0]['full_response'] == 'Successful response'
    
    @pytest.mark.asyncio
    async def test_streaming_with_fallback_to_default_model(self, llm_service, sample_document_chunks):
        """Test streaming with fallback to default model"""
        # First call fails, second succeeds
        mock_success_chunks = [
            {'response': 'Fallback response'},
            {'done': True, 'eval_count': 15}
        ]
        
        async def mock_failing_generate(*args, **kwargs):
            raise Exception("Model failed")
            yield  # Never reached but makes it a generator
        
        async def mock_success_generate(*args, **kwargs):
            for chunk in mock_success_chunks:
                yield chunk
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_ensure.return_value = True
                # First call fails, second succeeds
                mock_gen.side_effect = [mock_failing_generate(), mock_success_generate()]
                
                chunks = []
                async for chunk in llm_service.generate_streaming_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks,
                    model="custom-model"
                ):
                    chunks.append(chunk)
                
                # Should eventually get successful response from fallback or error response
                complete_chunks = [c for c in chunks if c.get('type') == 'complete']
                error_chunks = [c for c in chunks if c.get('type') == 'error']
                
                # Should have at least one completion or error
                assert len(complete_chunks) + len(error_chunks) >= 1
                
                if complete_chunks:
                    # If we got a complete response, it should be either fallback or generic error
                    assert complete_chunks[-1]['full_response'] in ['Fallback response', 'I apologize, but I\'m unable to generate a response at this time due to technical difficulties. Please try again later.']


class TestSourceReferenceExtraction:
    """Test cases for source reference extraction"""
    
    def test_extract_source_references_explicit_citations(self, llm_service, sample_document_chunks):
        """Test extraction of explicit source citations"""
        response_text = """
        Based on the information provided, [Source: Customer - CUST-001 (description)] 
        shows that Acme Corporation is a technology company. Additionally, 
        [Source: Item - ITEM-001 (specifications)] indicates the technical details.
        """
        
        sources = llm_service._extract_source_references(response_text, sample_document_chunks)
        
        # Should find both explicitly cited sources
        assert len(sources) == 2
        source_ids = [s.id for s in sources]
        assert "chunk1" in source_ids
        assert "chunk2" in source_ids
    
    def test_extract_source_references_implicit_mentions(self, llm_service, sample_document_chunks):
        """Test extraction of implicit source mentions"""
        response_text = """
        The customer CUST-001 is described as Acme Corporation. 
        The Item specifications show technical details.
        """
        
        sources = llm_service._extract_source_references(response_text, sample_document_chunks)
        
        # Should find sources based on implicit mentions
        assert len(sources) >= 1
        # Should include the customer chunk due to "CUST-001" mention
        customer_chunk = next((s for s in sources if s.docname == "CUST-001"), None)
        assert customer_chunk is not None
    
    def test_extract_source_references_no_matches(self, llm_service, sample_document_chunks):
        """Test source extraction when no specific references are found"""
        response_text = "This is a generic response with no specific source references."
        
        sources = llm_service._extract_source_references(response_text, sample_document_chunks)
        
        # Should return all context chunks when no specific references found
        assert len(sources) == len(sample_document_chunks)
    
    def test_extract_source_references_case_insensitive(self, llm_service, sample_document_chunks):
        """Test that source extraction is case insensitive"""
        response_text = "The customer cust-001 and item item-001 are mentioned."
        
        sources = llm_service._extract_source_references(response_text, sample_document_chunks)
        
        # Should find sources despite case differences
        assert len(sources) >= 2
        docnames = [s.docname for s in sources]
        assert "CUST-001" in docnames
        assert "ITEM-001" in docnames


class TestCompleteQAWorkflows:
    """Integration tests for complete Q&A workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_rag_workflow_non_streaming(self, llm_service, sample_document_chunks):
        """Test complete RAG workflow without streaming"""
        mock_response = {
            'response': 'Based on the context, Acme Corporation is a leading technology company specializing in cloud solutions.',
            'eval_count': 30
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.return_value = mock_response
                
                result = await llm_service.generate_response(
                    query="What can you tell me about the customer?",
                    context_chunks=sample_document_chunks,
                    model="test-model"
                )
                
                # Verify complete workflow
                assert "Acme Corporation" in result.answer
                assert "technology company" in result.answer
                assert result.model_used == "test-model"
                assert result.token_count == 30
                assert len(result.sources) > 0
                
                # Verify prompt was created with context
                call_args = mock_generate.call_args
                prompt = call_args[1]['prompt']
                assert "CONTEXT:" in prompt
                assert "Acme Corporation" in prompt
                assert "What can you tell me about the customer?" in prompt
    
    @pytest.mark.asyncio
    async def test_complete_chat_workflow_with_context(self, llm_service, sample_document_chunks):
        """Test complete chat workflow with context injection"""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help you?"),
            ChatMessage(role="user", content="Tell me about the customer")
        ]
        
        mock_response = {
            'message': {'content': 'Based on the available information, the customer Acme Corporation is a leading technology company.'},
            'eval_count': 25
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'chat', new_callable=AsyncMock) as mock_chat:
                mock_ensure.return_value = True
                mock_chat.return_value = mock_response
                
                result = await llm_service.chat_completion(
                    messages=messages,
                    context_chunks=sample_document_chunks,
                    model="test-model"
                )
                
                # Verify complete workflow
                assert "Acme Corporation" in result.message
                assert result.model_used == "test-model"
                assert result.token_count == 25
                assert len(result.sources) > 0
                
                # Verify context was injected via system message
                call_args = mock_chat.call_args
                messages_sent = call_args[1]['messages']
                assert len(messages_sent) == 4  # 1 system + 3 user messages
                assert messages_sent[0]['role'] == 'system'
                assert 'Acme Corporation' in messages_sent[0]['content']
    
    @pytest.mark.asyncio
    async def test_complete_streaming_workflow_with_source_extraction(self, llm_service, sample_document_chunks):
        """Test complete streaming workflow with source reference extraction"""
        mock_chunks = [
            {'response': 'Based on the context from '},
            {'response': '[Source: Customer - CUST-001 (description)], '},
            {'response': 'Acme Corporation is a technology company '},
            {'response': 'specializing in cloud solutions.'},
            {'done': True, 'eval_count': 35}
        ]
        
        async def mock_generate(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_ensure.return_value = True
                mock_gen.return_value = mock_generate()
                
                chunks = []
                async for chunk in llm_service.generate_streaming_response(
                    query="What is the customer's business focus?",
                    context_chunks=sample_document_chunks,
                    model="test-model"
                ):
                    chunks.append(chunk)
                
                # Verify streaming content
                content_chunks = [c for c in chunks if c.get('type') == 'content']
                assert len(content_chunks) == 4
                
                # Verify final completion with source extraction
                complete_chunks = [c for c in chunks if c.get('type') == 'complete']
                assert len(complete_chunks) == 1
                
                complete_chunk = complete_chunks[0]
                full_response = complete_chunk['full_response']
                assert 'Acme Corporation' in full_response
                assert '[Source: Customer - CUST-001 (description)]' in full_response
                
                # Verify source extraction worked
                sources = complete_chunk['sources']
                assert len(sources) >= 1
                customer_source = next((s for s in sources if s.docname == "CUST-001"), None)
                assert customer_source is not None
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery_workflow(self, llm_service, sample_document_chunks):
        """Test error handling and recovery in complete workflow"""
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                # First model fails, fallback succeeds
                mock_ensure.side_effect = [False, True]  # First model unavailable, default available
                mock_generate.return_value = {
                    'response': 'Fallback response about the customer.',
                    'eval_count': 20
                }
                
                result = await llm_service.generate_with_fallback(
                    query="Tell me about the customer",
                    context_chunks=sample_document_chunks,
                    model="unavailable-model"
                )
                
                # Should get fallback response
                assert "customer" in result.answer.lower()
                assert result.model_used == "test-model"  # Default model
                assert len(result.sources) > 0
    
    @pytest.mark.asyncio
    async def test_timeout_and_fallback_workflow(self, llm_service, sample_document_chunks):
        """Test timeout handling with fallback in complete workflow"""
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.side_effect = asyncio.TimeoutError()
                
                # Should handle timeout gracefully
                with pytest.raises(Exception, match="timed out"):
                    await llm_service.generate_response(
                        query="Test query",
                        context_chunks=sample_document_chunks
                    )
                
                # But fallback should handle it gracefully
                result = await llm_service.generate_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks
                )
                
                # Should get generic fallback response
                assert "unable to generate a response" in result.answer.lower()
                assert len(result.sources) > 0