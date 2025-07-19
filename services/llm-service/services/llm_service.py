"""
LLM Service - Core service for LLM operations using Ollama
"""

import os
import asyncio
from typing import List, Optional, Dict, Any, AsyncGenerator
import ollama
from ollama import AsyncClient
import json
import re

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
try:
    from models.document import DocumentChunk
except ImportError:
    # Fallback for testing
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from shared.models.document import DocumentChunk

try:
    from ..models.requests import ChatMessage
    from ..models.responses import GenerationResult, ChatResult
    from .prompt_templates import PromptTemplateManager
except ImportError:
    # Fallback for testing
    from models.requests import ChatMessage
    from models.responses import GenerationResult, ChatResult
    from services.prompt_templates import PromptTemplateManager


class LLMService:
    """Service for LLM operations using Ollama"""
    
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.default_model = os.getenv("DEFAULT_MODEL", "llama2")
        self.client = AsyncClient(host=self.ollama_url)
        self.prompt_manager = PromptTemplateManager()
        
        # Configuration
        self.max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
        self.default_temperature = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
        self.timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    
    async def health_check(self) -> bool:
        """Check if Ollama is available and responsive"""
        try:
            # Try to list models to verify connection
            await asyncio.wait_for(
                self.client.list(),
                timeout=5.0
            )
            return True
        except Exception as e:
            raise Exception(f"Ollama health check failed: {str(e)}")
    
    async def list_models(self) -> List[str]:
        """List available Ollama models"""
        try:
            response = await self.client.list()
            return [model['name'] for model in response['models']]
        except Exception as e:
            raise Exception(f"Failed to list models: {str(e)}")
    
    async def ensure_model_available(self, model: str) -> bool:
        """Ensure a model is available, pull if necessary"""
        try:
            available_models = await self.list_models()
            if model not in available_models:
                print(f"Model {model} not found, attempting to pull...")
                await self.client.pull(model)
                print(f"Successfully pulled model {model}")
            return True
        except Exception as e:
            print(f"Failed to ensure model {model} is available: {str(e)}")
            return False
    
    def _prepare_context(self, context_chunks: List[DocumentChunk]) -> str:
        """Prepare context from document chunks"""
        if not context_chunks:
            return ""
        
        context_parts = []
        total_length = 0
        
        for chunk in context_chunks:
            # Format each chunk with metadata
            chunk_text = f"""
Source: {chunk.doctype} - {chunk.docname} ({chunk.field_name})
Content: {chunk.content}
---"""
            
            # Check if adding this chunk would exceed context limit
            if total_length + len(chunk_text) > self.max_context_length:
                break
            
            context_parts.append(chunk_text)
            total_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    async def generate_response(
        self,
        query: str,
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> GenerationResult:
        """Generate a response using the LLM with RAG context"""
        
        # Use defaults if not specified
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        
        # Ensure model is available
        if not await self.ensure_model_available(model):
            # Fallback to default model
            model = self.default_model
            await self.ensure_model_available(model)
        
        # Prepare context from chunks
        context = self._prepare_context(context_chunks)
        
        # Generate prompt using template
        prompt = self.prompt_manager.create_rag_prompt(query, context)
        
        try:
            # Generate response with timeout
            response = await asyncio.wait_for(
                self.client.generate(
                    model=model,
                    prompt=prompt,
                    options={
                        'temperature': temperature,
                        'num_predict': max_tokens or -1,
                    }
                ),
                timeout=self.timeout_seconds
            )
            
            answer = response['response'].strip()
            
            # Extract token count if available
            token_count = None
            if 'eval_count' in response:
                token_count = response['eval_count']
            
            return GenerationResult(
                answer=answer,
                sources=context_chunks,
                model_used=model,
                token_count=token_count
            )
            
        except asyncio.TimeoutError:
            raise Exception(f"LLM generation timed out after {self.timeout_seconds} seconds")
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> ChatResult:
        """Complete a chat conversation with RAG context"""
        
        # Use defaults if not specified
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        
        # Ensure model is available
        if not await self.ensure_model_available(model):
            # Fallback to default model
            model = self.default_model
            await self.ensure_model_available(model)
        
        # Prepare context from chunks
        context = self._prepare_context(context_chunks)
        
        # Convert messages to Ollama format and inject context
        ollama_messages = []
        
        # Add system message with context if we have context
        if context:
            system_message = self.prompt_manager.create_system_message_with_context(context)
            ollama_messages.append({
                'role': 'system',
                'content': system_message
            })
        
        # Add conversation messages
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        try:
            # Generate chat response with timeout
            response = await asyncio.wait_for(
                self.client.chat(
                    model=model,
                    messages=ollama_messages,
                    options={
                        'temperature': temperature,
                        'num_predict': max_tokens or -1,
                    }
                ),
                timeout=self.timeout_seconds
            )
            
            message = response['message']['content'].strip()
            
            # Extract token count if available
            token_count = None
            if 'eval_count' in response:
                token_count = response['eval_count']
            
            return ChatResult(
                message=message,
                sources=context_chunks,
                model_used=model,
                token_count=token_count
            )
            
        except asyncio.TimeoutError:
            raise Exception(f"Chat completion timed out after {self.timeout_seconds} seconds")
        except Exception as e:
            raise Exception(f"Chat completion failed: {str(e)}")
    
    async def generate_with_fallback(
        self,
        query: str,
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> GenerationResult:
        """Generate response with fallback handling"""
        
        try:
            return await self.generate_response(
                query=query,
                context_chunks=context_chunks,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            print(f"Primary generation failed: {str(e)}")
            
            # Try with default model if different model was requested
            if model and model != self.default_model:
                try:
                    print(f"Falling back to default model: {self.default_model}")
                    return await self.generate_response(
                        query=query,
                        context_chunks=context_chunks,
                        model=self.default_model,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                except Exception as fallback_error:
                    print(f"Fallback generation also failed: {str(fallback_error)}")
            
            # Final fallback - return a generic response
            return GenerationResult(
                answer="I apologize, but I'm unable to generate a response at this time due to technical difficulties. Please try again later.",
                sources=context_chunks,
                model_used=model or self.default_model,
                token_count=None
            )
    
    def _extract_source_references(self, response_text: str, context_chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Extract and match source references from the response text"""
        referenced_sources = []
        
        # Create a mapping of source identifiers to chunks
        source_map = {}
        for chunk in context_chunks:
            # Create various identifiers that might be referenced
            identifiers = [
                f"{chunk.doctype} - {chunk.docname}",
                f"{chunk.doctype}-{chunk.docname}",
                chunk.docname,
                chunk.doctype,
                f"{chunk.doctype} {chunk.docname}",
                f"{chunk.field_name}"
            ]
            
            for identifier in identifiers:
                source_map[identifier.lower()] = chunk
        
        # Look for explicit source references in the response
        # Pattern 1: [Source: Document Type - Document Name (Field)]
        source_pattern1 = r'\[Source:\s*([^\]]+)\]'
        matches1 = re.findall(source_pattern1, response_text, re.IGNORECASE)
        
        for match in matches1:
            match_lower = match.lower().strip()
            if match_lower in source_map:
                chunk = source_map[match_lower]
                if chunk not in referenced_sources:
                    referenced_sources.append(chunk)
        
        # Pattern 2: Look for document names and types mentioned in text
        for identifier, chunk in source_map.items():
            if identifier in response_text.lower():
                if chunk not in referenced_sources:
                    referenced_sources.append(chunk)
        
        # If no specific references found, return all context chunks
        # as they were all potentially used
        if not referenced_sources:
            referenced_sources = context_chunks.copy()
        
        return referenced_sources
    
    async def generate_streaming_response(
        self,
        query: str,
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate a streaming response using the LLM with RAG context"""
        
        # Use defaults if not specified
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        
        # Ensure model is available
        if not await self.ensure_model_available(model):
            # Fallback to default model
            model = self.default_model
            await self.ensure_model_available(model)
        
        # Prepare context from chunks
        context = self._prepare_context(context_chunks)
        
        # Generate prompt using template
        prompt = self.prompt_manager.create_rag_prompt(query, context)
        
        try:
            # Start streaming generation
            full_response = ""
            token_count = 0
            
            stream = await self.client.generate(
                model=model,
                prompt=prompt,
                stream=True,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens or -1,
                }
            )
            
            async for chunk in stream:
                if 'response' in chunk:
                    chunk_text = chunk['response']
                    full_response += chunk_text
                    
                    # Yield the streaming chunk
                    yield {
                        'type': 'content',
                        'content': chunk_text,
                        'model_used': model
                    }
                
                # Track token count if available
                if 'eval_count' in chunk:
                    token_count = chunk['eval_count']
                
                # Check if this is the final chunk
                if chunk.get('done', False):
                    # Extract source references from the complete response
                    referenced_sources = self._extract_source_references(full_response, context_chunks)
                    
                    # Yield final metadata
                    yield {
                        'type': 'complete',
                        'full_response': full_response.strip(),
                        'sources': referenced_sources,
                        'model_used': model,
                        'token_count': token_count
                    }
                    break
            
        except asyncio.TimeoutError:
            yield {
                'type': 'error',
                'error': f"LLM generation timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            yield {
                'type': 'error',
                'error': f"LLM generation failed: {str(e)}"
            }
    
    async def chat_streaming_completion(
        self,
        messages: List[ChatMessage],
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Complete a chat conversation with streaming and RAG context"""
        
        # Use defaults if not specified
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        
        # Ensure model is available
        if not await self.ensure_model_available(model):
            # Fallback to default model
            model = self.default_model
            await self.ensure_model_available(model)
        
        # Prepare context from chunks
        context = self._prepare_context(context_chunks)
        
        # Convert messages to Ollama format and inject context
        ollama_messages = []
        
        # Add system message with context if we have context
        if context:
            system_message = self.prompt_manager.create_system_message_with_context(context)
            ollama_messages.append({
                'role': 'system',
                'content': system_message
            })
        
        # Add conversation messages
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        try:
            # Start streaming chat completion
            full_response = ""
            token_count = 0
            
            stream = await self.client.chat(
                model=model,
                messages=ollama_messages,
                stream=True,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens or -1,
                }
            )
            
            async for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    chunk_text = chunk['message']['content']
                    full_response += chunk_text
                    
                    # Yield the streaming chunk
                    yield {
                        'type': 'content',
                        'content': chunk_text,
                        'model_used': model
                    }
                
                # Track token count if available
                if 'eval_count' in chunk:
                    token_count = chunk['eval_count']
                
                # Check if this is the final chunk
                if chunk.get('done', False):
                    # Extract source references from the complete response
                    referenced_sources = self._extract_source_references(full_response, context_chunks)
                    
                    # Yield final metadata
                    yield {
                        'type': 'complete',
                        'full_response': full_response.strip(),
                        'sources': referenced_sources,
                        'model_used': model,
                        'token_count': token_count
                    }
                    break
            
        except asyncio.TimeoutError:
            yield {
                'type': 'error',
                'error': f"Chat completion timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            yield {
                'type': 'error',
                'error': f"Chat completion failed: {str(e)}"
            }
    
    async def generate_streaming_with_fallback(
        self,
        query: str,
        context_chunks: List[DocumentChunk],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with fallback handling"""
        
        try:
            async for chunk in self.generate_streaming_response(
                query=query,
                context_chunks=context_chunks,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                yield chunk
                
                # If we get an error, try fallback
                if chunk.get('type') == 'error':
                    if model and model != self.default_model:
                        print(f"Streaming generation failed, trying fallback to {self.default_model}")
                        async for fallback_chunk in self.generate_streaming_response(
                            query=query,
                            context_chunks=context_chunks,
                            model=self.default_model,
                            temperature=temperature,
                            max_tokens=max_tokens
                        ):
                            yield fallback_chunk
                            if fallback_chunk.get('type') in ['complete', 'error']:
                                break
                    else:
                        # Final fallback - yield generic error response
                        yield {
                            'type': 'complete',
                            'full_response': "I apologize, but I'm unable to generate a response at this time due to technical difficulties. Please try again later.",
                            'sources': context_chunks,
                            'model_used': model or self.default_model,
                            'token_count': None
                        }
                    break
                    
        except Exception as e:
            yield {
                'type': 'error',
                'error': f"Streaming generation failed: {str(e)}"
            }