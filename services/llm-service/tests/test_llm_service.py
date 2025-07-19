"""
Unit tests for LLM Service
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
import os

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
            content="This is a sample customer description with important details.",
            metadata=DocumentMetadata(
                chunk_index=0,
                total_chunks=1,
                timestamp=datetime.utcnow(),
                content_length=65,
                word_count=10
            )
        ),
        DocumentChunk(
            id="chunk2",
            doctype="Item",
            docname="ITEM-001",
            field_name="specifications",
            content="Technical specifications for the product including dimensions and materials.",
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


class TestLLMService:
    """Test cases for LLM Service"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, llm_service):
        """Test successful health check"""
        with patch.object(llm_service.client, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {'models': []}
            
            result = await llm_service.health_check()
            assert result is True
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, llm_service):
        """Test health check failure"""
        with patch.object(llm_service.client, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Ollama health check failed"):
                await llm_service.health_check()
    
    @pytest.mark.asyncio
    async def test_list_models(self, llm_service):
        """Test listing available models"""
        mock_response = {
            'models': [
                {'name': 'llama2'},
                {'name': 'mistral'},
                {'name': 'codellama'}
            ]
        }
        
        with patch.object(llm_service.client, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response
            
            models = await llm_service.list_models()
            assert models == ['llama2', 'mistral', 'codellama']
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_model_available_exists(self, llm_service):
        """Test ensuring model availability when model exists"""
        with patch.object(llm_service, 'list_models', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ['llama2', 'mistral']
            
            result = await llm_service.ensure_model_available('llama2')
            assert result is True
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_model_available_pull_needed(self, llm_service):
        """Test ensuring model availability when pull is needed"""
        with patch.object(llm_service, 'list_models', new_callable=AsyncMock) as mock_list:
            with patch.object(llm_service.client, 'pull', new_callable=AsyncMock) as mock_pull:
                mock_list.return_value = ['llama2']  # Model not in list
                
                result = await llm_service.ensure_model_available('mistral')
                assert result is True
                mock_list.assert_called_once()
                mock_pull.assert_called_once_with('mistral')
    
    def test_prepare_context(self, llm_service, sample_document_chunks):
        """Test context preparation from document chunks"""
        context = llm_service._prepare_context(sample_document_chunks)
        
        assert "Source: Customer - CUST-001 (description)" in context
        assert "This is a sample customer description" in context
        assert "Source: Item - ITEM-001 (specifications)" in context
        assert "Technical specifications for the product" in context
        assert "---" in context  # Separator
    
    def test_prepare_context_empty(self, llm_service):
        """Test context preparation with empty chunks"""
        context = llm_service._prepare_context([])
        assert context == ""
    
    def test_prepare_context_length_limit(self, llm_service):
        """Test context preparation respects length limits"""
        # Create a chunk that would exceed the limit
        large_chunk = DocumentChunk(
            id="large",
            doctype="Test",
            docname="TEST-001",
            field_name="content",
            content="x" * 2000,  # Very large content
            metadata=DocumentMetadata(
                chunk_index=0,
                total_chunks=1,
                timestamp=datetime.utcnow(),
                content_length=2000,
                word_count=1
            )
        )
        
        context = llm_service._prepare_context([large_chunk])
        # Should be truncated due to max_context_length=1000
        assert len(context) <= llm_service.max_context_length
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, llm_service, sample_document_chunks):
        """Test successful response generation"""
        mock_response = {
            'response': 'This is a generated response based on the context.',
            'eval_count': 25
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.return_value = mock_response
                
                result = await llm_service.generate_response(
                    query="What is the customer description?",
                    context_chunks=sample_document_chunks,
                    model="test-model"
                )
                
                assert result.answer == "This is a generated response based on the context."
                assert result.model_used == "test-model"
                assert result.token_count == 25
                assert result.sources == sample_document_chunks
                
                mock_ensure.assert_called_once_with("test-model")
                mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_response_model_fallback(self, llm_service, sample_document_chunks):
        """Test response generation with model fallback"""
        mock_response = {
            'response': 'Fallback response',
            'eval_count': 15
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                # First call (requested model) fails, second call (default) succeeds
                mock_ensure.side_effect = [False, True]
                mock_generate.return_value = mock_response
                
                result = await llm_service.generate_response(
                    query="Test query",
                    context_chunks=sample_document_chunks,
                    model="unavailable-model"
                )
                
                assert result.model_used == "test-model"  # Default model
                assert mock_ensure.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_response_timeout(self, llm_service, sample_document_chunks):
        """Test response generation timeout handling"""
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.side_effect = asyncio.TimeoutError()
                
                with pytest.raises(Exception, match="LLM generation timed out"):
                    await llm_service.generate_response(
                        query="Test query",
                        context_chunks=sample_document_chunks
                    )
    
    @pytest.mark.asyncio
    async def test_chat_completion_success(self, llm_service, sample_document_chunks):
        """Test successful chat completion"""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
            ChatMessage(role="user", content="What can you tell me about the customer?")
        ]
        
        mock_response = {
            'message': {'content': 'Based on the context, I can tell you about the customer.'},
            'eval_count': 30
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
                
                assert result.message == "Based on the context, I can tell you about the customer."
                assert result.model_used == "test-model"
                assert result.token_count == 30
                assert result.sources == sample_document_chunks
                
                mock_ensure.assert_called_once_with("test-model")
                mock_chat.assert_called_once()
                
                # Verify the messages passed to chat include system message with context
                call_args = mock_chat.call_args
                messages_sent = call_args[1]['messages']
                assert len(messages_sent) == 4  # 1 system + 3 user messages
                assert messages_sent[0]['role'] == 'system'
                assert 'Customer - CUST-001' in messages_sent[0]['content']
    
    @pytest.mark.asyncio
    async def test_chat_completion_no_context(self, llm_service):
        """Test chat completion without context"""
        messages = [ChatMessage(role="user", content="Hello")]
        
        mock_response = {
            'message': {'content': 'Hello! How can I help you?'},
            'eval_count': 10
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'chat', new_callable=AsyncMock) as mock_chat:
                mock_ensure.return_value = True
                mock_chat.return_value = mock_response
                
                result = await llm_service.chat_completion(
                    messages=messages,
                    context_chunks=[],  # No context
                    model="test-model"
                )
                
                assert result.message == "Hello! How can I help you?"
                
                # Verify no system message was added when no context
                call_args = mock_chat.call_args
                messages_sent = call_args[1]['messages']
                assert len(messages_sent) == 1
                assert messages_sent[0]['role'] == 'user'
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback_success(self, llm_service, sample_document_chunks):
        """Test generate with fallback - success case"""
        mock_response = {
            'response': 'Successful response',
            'eval_count': 20
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.return_value = mock_response
                
                result = await llm_service.generate_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks
                )
                
                assert result.answer == "Successful response"
                assert result.token_count == 20
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback_to_default_model(self, llm_service, sample_document_chunks):
        """Test generate with fallback to default model"""
        mock_response = {
            'response': 'Fallback response',
            'eval_count': 15
        }
        
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                # First call fails, second succeeds
                mock_ensure.return_value = True
                mock_generate.side_effect = [Exception("First model failed"), mock_response]
                
                result = await llm_service.generate_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks,
                    model="custom-model"
                )
                
                assert result.answer == "Fallback response"
                assert result.model_used == "test-model"  # Default model
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback_complete_failure(self, llm_service, sample_document_chunks):
        """Test generate with fallback when everything fails"""
        with patch.object(llm_service, 'ensure_model_available', new_callable=AsyncMock) as mock_ensure:
            with patch.object(llm_service.client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_ensure.return_value = True
                mock_generate.side_effect = Exception("All models failed")
                
                result = await llm_service.generate_with_fallback(
                    query="Test query",
                    context_chunks=sample_document_chunks,
                    model="custom-model"
                )
                
                # Should return generic error message
                assert "unable to generate a response" in result.answer.lower()
                assert result.sources == sample_document_chunks