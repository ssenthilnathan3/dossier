"""
Unit tests for Prompt Template Manager
"""

import pytest
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.prompt_templates import PromptTemplateManager


class TestPromptTemplateManager:
    """Test cases for Prompt Template Manager"""
    
    @pytest.fixture
    def prompt_manager(self):
        """Prompt manager instance for testing"""
        return PromptTemplateManager()
    
    @pytest.fixture
    def sample_context(self):
        """Sample context for testing"""
        return """
Source: Customer - CUST-001 (description)
Content: This is a sample customer with important business details.
---
Source: Item - ITEM-001 (specifications)
Content: Technical specifications including dimensions and materials.
---"""
    
    def test_initialization(self, prompt_manager):
        """Test prompt manager initialization"""
        assert 'rag_qa' in prompt_manager.templates
        assert 'system_with_context' in prompt_manager.templates
        assert 'fallback' in prompt_manager.templates
        assert len(prompt_manager.templates) >= 3
    
    def test_create_rag_prompt_with_context(self, prompt_manager, sample_context):
        """Test RAG prompt creation with context"""
        query = "What are the customer details?"
        prompt = prompt_manager.create_rag_prompt(query, sample_context)
        
        assert "CONTEXT:" in prompt
        assert sample_context in prompt
        assert "QUESTION: What are the customer details?" in prompt
        assert "ANSWER:" in prompt
        assert "using ONLY the information provided" in prompt
    
    def test_create_rag_prompt_without_context(self, prompt_manager):
        """Test RAG prompt creation without context"""
        query = "What is the weather like?"
        prompt = prompt_manager.create_rag_prompt(query, "")
        
        # Should use fallback template
        assert "QUESTION: What is the weather like?" in prompt
        assert "CONTEXT:" not in prompt
        assert "helpful assistant" in prompt
    
    def test_create_system_message_with_context(self, prompt_manager, sample_context):
        """Test system message creation with context"""
        system_message = prompt_manager.create_system_message_with_context(sample_context)
        
        assert "helpful assistant with access to relevant document information" in system_message
        assert "CONTEXT:" in system_message
        assert sample_context in system_message
        assert "Use the provided context when relevant" in system_message
    
    def test_create_custom_prompt(self, prompt_manager):
        """Test custom prompt creation"""
        # Test with existing template
        prompt = prompt_manager.create_custom_prompt(
            'fallback',
            query="Test question"
        )
        assert "Test question" in prompt
        
        # Test with non-existent template
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            prompt_manager.create_custom_prompt('nonexistent', query="Test")
    
    def test_add_template(self, prompt_manager):
        """Test adding new template"""
        new_template = "Custom template with {variable}"
        prompt_manager.add_template('custom', new_template)
        
        assert 'custom' in prompt_manager.templates
        assert prompt_manager.get_template('custom') == new_template
        
        # Test using the new template
        prompt = prompt_manager.create_custom_prompt('custom', variable="test value")
        assert "Custom template with test value" in prompt
    
    def test_get_template(self, prompt_manager):
        """Test getting template by name"""
        rag_template = prompt_manager.get_template('rag_qa')
        assert rag_template is not None
        assert "CONTEXT:" in rag_template
        
        # Test non-existent template
        assert prompt_manager.get_template('nonexistent') is None
    
    def test_list_templates(self, prompt_manager):
        """Test listing all templates"""
        templates = prompt_manager.list_templates()
        assert isinstance(templates, list)
        assert 'rag_qa' in templates
        assert 'system_with_context' in templates
        assert 'fallback' in templates
    
    def test_create_context_aware_prompt_basic(self, prompt_manager, sample_context):
        """Test context-aware prompt creation (basic)"""
        query = "What are the specifications?"
        prompt = prompt_manager.create_context_aware_prompt(query, sample_context)
        
        # Should be same as basic RAG prompt when no history/preferences
        basic_prompt = prompt_manager.create_rag_prompt(query, sample_context)
        assert prompt == basic_prompt
    
    def test_create_context_aware_prompt_with_history(self, prompt_manager, sample_context):
        """Test context-aware prompt with conversation history"""
        query = "What about the materials?"
        history = [
            {'role': 'user', 'content': 'Tell me about the customer'},
            {'role': 'assistant', 'content': 'The customer has important business details'},
            {'role': 'user', 'content': 'What about specifications?'},
            {'role': 'assistant', 'content': 'The specifications include dimensions'}
        ]
        
        prompt = prompt_manager.create_context_aware_prompt(
            query, sample_context, conversation_history=history
        )
        
        assert "RECENT CONVERSATION:" in prompt
        assert "USER: What about specifications?" in prompt
        assert "ASSISTANT: The specifications include dimensions" in prompt
        # Should only include last 3 messages
        assert "Tell me about the customer" not in prompt
    
    def test_create_context_aware_prompt_with_preferences(self, prompt_manager, sample_context):
        """Test context-aware prompt with user preferences"""
        query = "Explain the customer details"
        preferences = {
            'detail_level': 'comprehensive',
            'response_style': 'technical'
        }
        
        prompt = prompt_manager.create_context_aware_prompt(
            query, sample_context, user_preferences=preferences
        )
        
        assert "USER PREFERENCES:" in prompt
        assert "Detail level: comprehensive" in prompt
        assert "Response style: technical" in prompt
    
    def test_create_context_aware_prompt_full(self, prompt_manager, sample_context):
        """Test context-aware prompt with all features"""
        query = "What should I know?"
        history = [
            {'role': 'user', 'content': 'Previous question'},
            {'role': 'assistant', 'content': 'Previous answer'}
        ]
        preferences = {
            'detail_level': 'brief',
            'response_style': 'casual'
        }
        
        prompt = prompt_manager.create_context_aware_prompt(
            query, sample_context, 
            conversation_history=history,
            user_preferences=preferences
        )
        
        assert "USER PREFERENCES:" in prompt
        assert "RECENT CONVERSATION:" in prompt
        assert "CONTEXT:" in prompt
        assert "QUESTION: What should I know?" in prompt
    
    def test_create_source_citation_prompt(self, prompt_manager, sample_context):
        """Test source citation prompt creation"""
        query = "What information is available?"
        prompt = prompt_manager.create_source_citation_prompt(query, sample_context)
        
        assert "research assistant" in prompt
        assert "proper source citations" in prompt
        assert "[Source: Document Type - Document Name (Field)]" in prompt
        assert sample_context in prompt
        assert "ANSWER (with citations):" in prompt
    
    def test_create_summarization_prompt_basic(self, prompt_manager):
        """Test basic summarization prompt"""
        content = "This is a long document that needs to be summarized for clarity."
        prompt = prompt_manager.create_summarization_prompt(content)
        
        assert "clear and concise summary" in prompt
        assert content in prompt
        assert "SUMMARY:" in prompt
    
    def test_create_summarization_prompt_with_focus(self, prompt_manager):
        """Test summarization prompt with focus"""
        content = "Document with technical details and business information."
        focus = "technical aspects"
        prompt = prompt_manager.create_summarization_prompt(content, focus)
        
        assert "focusing on: technical aspects" in prompt
        assert content in prompt
        assert "FOCUSED SUMMARY:" in prompt
    
    def test_template_content_validation(self, prompt_manager):
        """Test that templates contain expected content"""
        rag_template = prompt_manager.get_template('rag_qa')
        assert "{context}" in rag_template
        assert "{query}" in rag_template
        assert "ONLY the information provided" in rag_template
        
        system_template = prompt_manager.get_template('system_with_context')
        assert "{context}" in system_template
        assert "helpful assistant" in system_template
        
        fallback_template = prompt_manager.get_template('fallback')
        assert "{query}" in fallback_template
        assert "helpful assistant" in fallback_template
    
    def test_prompt_formatting_edge_cases(self, prompt_manager):
        """Test prompt formatting with edge cases"""
        # Empty query
        prompt = prompt_manager.create_rag_prompt("", "Some context")
        assert "QUESTION:" in prompt
        
        # Very long context (should still work)
        long_context = "Context " * 1000
        prompt = prompt_manager.create_rag_prompt("Test query", long_context)
        assert long_context in prompt
        
        # Special characters in query
        special_query = "What about {special} characters & symbols?"
        prompt = prompt_manager.create_rag_prompt(special_query, "Context")
        assert special_query in prompt