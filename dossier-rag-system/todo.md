# Implementation Plan

- [x] 1. Set up project structure and development environment
  - Create Docker-first monorepo structure with services directories
  - Set up development Docker Compose with all required services
  - Configure shared TypeScript/Python tooling and linting

- [x] 2. Implement core data models and configuration system
  - [x] 2.1 Create shared data models and interfaces
    - Define TypeScript interfaces for all data models (DoctypeConfig, DocumentChunk, QueryRequest/Response)
    - Create Python Pydantic models matching TypeScript interfaces
    - Write validation functions for all data models

  - [x] 2.2 Implement configuration management system
    - Create PostgreSQL schema for Doctype configurations
    - Implement configuration CRUD operations with validation
    - Create configuration loading and caching mechanisms
    - Write unit tests for configuration management

- [-] 3. Build webhook handler service
  - [x] 3.1 Create webhook receiver with validation
    - Implement Express.js webhook endpoint with HMAC signature verification
    - Add request validation and error handling
    - Create webhook payload parsing and normalization
    - Write unit tests for webhook validation and parsing

  - [x] 3.2 Implement webhook queue integration
    - Set up Redis pub/sub for webhook message queuing
    - Create message publishing with retry logic
    - Add webhook processing status tracking
    - Write integration tests for queue operations

- [-] 4. Develop document ingestion service
  - [x] 4.1 Create Frappe document fetcher
    - Implement Frappe API client with authentication
    - Create document fetching with field selection based on configuration
    - Add error handling for API failures and missing documents
    - Write unit tests for document fetching scenarios

  - [x] 4.2 Implement batch processing for manual ingestion
    - Resolve the errors in integration test for manual ingestion
    - Create manual ingestion API endpoints with progress tracking
    - Implement batch document processing with configurable batch sizes
    - Add duplicate detection and update logic
    - Create ingestion summary reporting
    - Write integration tests for manual ingestion workflows

- [x] 5. Build intelligent chunking service
  - [x] 5.1 Implement recursive text splitting
    - Create text chunking with LangChain recursive splitter
    - Implement semantic boundary detection (sentences, paragraphs)
    - Add configurable chunk size and overlap handling
    - Write unit tests for various text chunking scenarios

  - [x] 5.2 Add chunk metadata and edge case handling
    - Implement metadata preservation during chunking
    - Add handling for empty fields and too-short content
    - Create chunk validation and quality checks
    - Write unit tests for edge cases and metadata handling

- [-] 6. Create embedding service with vector storage
  - [ ] 6.1 Implement BGE-small embedding generation
    - Set up sentence-transformers with bge-small model
    - Create batch embedding generation with error handling
    - Implement embedding caching and deduplication
    - Write unit tests for embedding generation

  - [x] 6.2 Integrate Qdrant vector database
    - Set up Qdrant client with connection management
    - Implement vector storage with metadata indexing
    - Add vector update and deletion operations
    - Create connection retry logic with exponential backoff
    - Write integration tests for vector operations

- [x] 7. Build query and retrieval service
  - [x] 7.1 Implement semantic search functionality
    - Create query embedding and similarity search in Qdrant
    - Implement top-k retrieval with configurable parameters
    - Add result filtering and ranking logic
    - Write unit tests for search functionality

  - [x] 7.2 Add search result processing and metadata
    - Implement result formatting with source metadata
    - Create search result caching for performance
    - Add search analytics and logging
    - Handle empty result scenarios gracefully
    - Write integration tests for complete search workflows

- [x] 8. Develop LLM service for Q&A
  - [x] 8.1 Integrate Ollama for local LLM inference
    - Set up Ollama client with model management
    - Create prompt templates for RAG responses
    - Implement context injection from retrieved chunks
    - Write unit tests for prompt generation and LLM calls

  - [x] 8.2 Add response streaming and source references
    - Implement streaming response generation
    - Create source reference extraction and formatting
    - Add response timeout and fallback handling
    - Write integration tests for complete Q&A workflows

- [-] 9. Create React chat interface
  - [x] 9.1 Build core chat UI components
    - Create React chat interface with TypeScript
    - Implement Tailwind CSS styling for responsive design
    - Add message components with typing indicators
    - Write component unit tests with React Testing Library

  - [x] 9.2 Implement real-time features and source highlighting
    - Add WebSocket integration for streaming responses
    - Create source reference highlighting and linking
    - Implement click-to-expand for document context
    - Add mobile-responsive design optimizations
    - Write end-to-end tests for chat interactions

- [x] 10. Implement production deployment and monitoring
  - [x] 10.1 Create Docker containers and orchestration
    - Build optimized Docker images for all services
    - Create production Docker Compose configuration
    - Add health check endpoints for all services
    - Implement graceful shutdown handling
    - Write deployment validation tests

  - [x] 10.2 Add monitoring, logging, and error handling
    - Implement structured JSON logging across all services
    - Add Prometheus metrics collection
    - Create comprehensive error handling and recovery
    - Set up distributed tracing for request flows
    - Write monitoring and alerting configuration

- [x] 11. Create API gateway and service integration
  - [x] 11.1 Implement API gateway with authentication
    - Create API gateway with JWT authentication
    - Add rate limiting and request validation
    - Implement service discovery and load balancing
    - Write API integration tests

  - [x] 11.2 Wire all services together with end-to-end testing
    - Create service-to-service communication protocols
    - Implement complete data flow from webhook to chat response
    - Add comprehensive end-to-end test suite
    - Create system performance benchmarks
    - Write deployment and configuration documentation
