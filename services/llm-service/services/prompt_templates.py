"""
Prompt Template Manager - Handles prompt generation for RAG responses
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class PromptTemplateManager:
    """Manages prompt templates for different LLM use cases"""
    
    def __init__(self):
        self.templates = {
            'rag_qa': self._get_rag_qa_template(),
            'system_with_context': self._get_system_context_template(),
            'fallback': self._get_fallback_template()
        }
    
    def _get_rag_qa_template(self) -> str:
        """Template for RAG-based question answering"""
        return """You are a helpful assistant that answers questions based on the provided context from documents. 

CONTEXT:
{context}

INSTRUCTIONS:
- Answer the question using ONLY the information provided in the context above
- If the context doesn't contain enough information to answer the question, say so clearly
- Be specific and cite which documents or sections you're referencing
- Provide a comprehensive answer when possible
- If multiple sources provide relevant information, synthesize them coherently
- Maintain a professional and helpful tone

QUESTION: {query}

ANSWER:"""
    
    def _get_system_context_template(self) -> str:
        """Template for system message with context in chat mode"""
        return """You are a helpful assistant with access to relevant document information. Use the following context to inform your responses:

CONTEXT:
{context}

When answering questions:
- Use the provided context when relevant
- Be specific about which documents or sections you're referencing
- If the context doesn't contain relevant information, acknowledge this
- Provide helpful and accurate responses
- Maintain a conversational tone appropriate for chat"""
    
    def _get_fallback_template(self) -> str:
        """Template for when no context is available"""
        return """You are a helpful assistant. Please answer the following question to the best of your ability:

QUESTION: {query}

ANSWER:"""
    
    def create_rag_prompt(self, query: str, context: str) -> str:
        """Create a RAG prompt with query and context"""
        if not context.strip():
            # Use fallback template when no context
            return self.templates['fallback'].format(query=query)
        
        return self.templates['rag_qa'].format(
            context=context,
            query=query
        )
    
    def create_system_message_with_context(self, context: str) -> str:
        """Create a system message with context for chat mode"""
        return self.templates['system_with_context'].format(context=context)
    
    def create_custom_prompt(
        self, 
        template_name: str, 
        **kwargs
    ) -> str:
        """Create a prompt using a custom template"""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        return self.templates[template_name].format(**kwargs)
    
    def add_template(self, name: str, template: str) -> None:
        """Add a new template"""
        self.templates[name] = template
    
    def get_template(self, name: str) -> Optional[str]:
        """Get a template by name"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List all available template names"""
        return list(self.templates.keys())
    
    def create_context_aware_prompt(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a more sophisticated prompt with conversation history and preferences"""
        
        base_prompt = self.create_rag_prompt(query, context)
        
        # Add conversation history if available
        if conversation_history:
            history_text = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in conversation_history[-3:]  # Last 3 messages for context
            ])
            base_prompt = f"RECENT CONVERSATION:\n{history_text}\n\n{base_prompt}"
        
        # Add user preferences if available
        if user_preferences:
            prefs_text = []
            if user_preferences.get('detail_level'):
                prefs_text.append(f"Detail level: {user_preferences['detail_level']}")
            if user_preferences.get('response_style'):
                prefs_text.append(f"Response style: {user_preferences['response_style']}")
            
            if prefs_text:
                prefs_section = f"USER PREFERENCES:\n{', '.join(prefs_text)}\n\n"
                base_prompt = prefs_section + base_prompt
        
        return base_prompt
    
    def create_source_citation_prompt(self, query: str, context: str) -> str:
        """Create a prompt that emphasizes source citations"""
        return f"""You are a research assistant that provides accurate answers with proper source citations.

CONTEXT:
{context}

INSTRUCTIONS:
- Answer the question using the provided context
- For each piece of information, cite the specific source document
- Use format: [Source: Document Type - Document Name (Field)]
- If information comes from multiple sources, cite all relevant sources
- If the context is insufficient, clearly state what information is missing
- Organize your answer clearly with proper citations

QUESTION: {query}

ANSWER (with citations):"""
    
    def create_summarization_prompt(self, content: str, focus: Optional[str] = None) -> str:
        """Create a prompt for summarizing content"""
        base_prompt = f"""Please provide a clear and concise summary of the following content:

CONTENT:
{content}

SUMMARY:"""
        
        if focus:
            base_prompt = f"""Please provide a clear and concise summary of the following content, focusing on: {focus}

CONTENT:
{content}

FOCUSED SUMMARY:"""
        
        return base_prompt