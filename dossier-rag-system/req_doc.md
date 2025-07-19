# Requirements Document

## Introduction

Dossier is a lightweight, open-source Live RAG (Retrieval-Augmented Generation) system designed specifically for Frappe documents. The system provides real-time document ingestion, intelligent chunking, semantic search, and natural language Q&A capabilities through a modern chat interface. It's built to be production-ready, Docker-first, and easily extensible for any Frappe deployment.

## Requirements

### Requirement 1: Live Document Synchronization

**User Story:** As a Frappe administrator, I want the system to automatically ingest document updates in real-time, so that the RAG system always has the latest information without manual intervention.

#### Acceptance Criteria

1. WHEN a Frappe document is created, updated, or deleted THEN the system SHALL automatically receive the change via webhook
2. WHEN a webhook is received THEN the system SHALL process the document within 30 seconds
3. WHEN processing fails THEN the system SHALL retry with exponential backoff and log the error
4. IF a document type is not configured for ingestion THEN the system SHALL ignore the webhook gracefully

### Requirement 2: Manual Document Ingestion

**User Story:** As a system administrator, I want to manually trigger document ingestion for specific Doctypes and filters, so that I can backfill historical data or handle edge cases.

#### Acceptance Criteria

1. WHEN I specify a Doctype and optional filters THEN the system SHALL ingest all matching documents
2. WHEN manual ingestion is triggered THEN the system SHALL show progress indicators and completion status
3. IF duplicate documents are processed THEN the system SHALL update existing embeddings rather than create duplicates
4. WHEN ingestion completes THEN the system SHALL provide a summary of processed, updated, and failed documents

### Requirement 3: Configurable Document Processing

**User Story:** As a system administrator, I want to configure which Doctype fields are indexed and what filters are applied, so that I can control what information is available for search.

#### Acceptance Criteria

1. WHEN I configure a Doctype THEN the system SHALL allow me to select specific fields for indexing
2. WHEN I set filters for a Doctype THEN the system SHALL only process documents matching those filters
3. WHEN configuration changes are made THEN the system SHALL apply them to new ingestions without requiring restart
4. IF a configured field doesn't exist on a document THEN the system SHALL skip it gracefully and log a warning

### Requirement 4: Intelligent Text Chunking

**User Story:** As a system user, I want document content to be intelligently chunked while preserving semantic meaning, so that search results are contextually relevant and complete.

#### Acceptance Criteria

1. WHEN processing document text THEN the system SHALL use recursive splitting to preserve semantic integrity
2. WHEN chunk size limits are reached THEN the system SHALL split at natural boundaries (sentences, paragraphs)
3. WHEN chunks are created THEN the system SHALL include configurable overlap between adjacent chunks
4. IF a field is empty or too short THEN the system SHALL handle it gracefully without creating invalid chunks
5. WHEN chunking completes THEN each chunk SHALL retain metadata about its source document and field

### Requirement 5: Lightweight Vector Embeddings

**User Story:** As a system administrator, I want the system to generate high-quality embeddings efficiently using lightweight models, so that it can run in resource-constrained environments.

#### Acceptance Criteria

1. WHEN generating embeddings THEN the system SHALL use the bge-small model for efficiency
2. WHEN chunks are embedded THEN the system SHALL include relevant metadata (Doctype, DocName, field, timestamp)
3. WHEN embeddings are generated THEN the system SHALL store them in Qdrant vector database
4. IF Qdrant is unavailable THEN the system SHALL queue embeddings and retry with backoff
5. WHEN storing vectors THEN the system SHALL support both self-hosted and cloud Qdrant instances

### Requirement 6: Contextual Search and Retrieval

**User Story:** As an end user, I want to search for information using natural language and receive relevant document chunks with source metadata, so that I can quickly find and verify information.

#### Acceptance Criteria

1. WHEN I submit a search query THEN the system SHALL perform semantic similarity search in Qdrant
2. WHEN search results are returned THEN the system SHALL include top-k most relevant chunks (configurable k)
3. WHEN results are provided THEN each chunk SHALL include source metadata (Doctype, DocName, field name, timestamp)
4. WHEN search completes THEN results SHALL be returned in under 2 seconds for typical queries
5. IF no relevant results are found THEN the system SHALL return an appropriate message

### Requirement 7: Natural Language Q&A

**User Story:** As an end user, I want to ask questions in natural language and receive comprehensive answers with source references, so that I can get insights from my Frappe data conversationally.

#### Acceptance Criteria

1. WHEN I ask a question THEN the system SHALL retrieve relevant chunks and generate a natural language answer
2. WHEN generating answers THEN the system SHALL use lightweight Ollama LLMs (mistral, llama3, etc.)
3. WHEN an answer is provided THEN the system SHALL include references to source documents and specific chunks
4. WHEN generating responses THEN the system SHALL stream the answer in real-time for better user experience
5. IF the LLM cannot answer based on available context THEN the system SHALL clearly state the limitation

### Requirement 8: Modern Chat Interface

**User Story:** As an end user, I want a responsive, real-time chat interface that clearly shows AI answers and their supporting sources, so that I can interact naturally with the system.

#### Acceptance Criteria

1. WHEN I access the interface THEN the system SHALL provide a React-based chat UI with Tailwind styling
2. WHEN I send a message THEN the interface SHALL show real-time typing indicators and streaming responses
3. WHEN answers are displayed THEN the interface SHALL highlight and link to supporting source snippets
4. WHEN I click on source references THEN the interface SHALL show the original document context
5. WHEN using the interface THEN it SHALL be responsive and work well on desktop and mobile devices

### Requirement 9: Production-Ready Deployment

**User Story:** As a DevOps engineer, I want to deploy the system using Docker with proper configuration management, so that it can run reliably in production environments.

#### Acceptance Criteria

1. WHEN deploying the system THEN it SHALL be packaged as Docker containers in a monorepo structure
2. WHEN configuring the system THEN all settings SHALL be manageable via environment variables or config files
3. WHEN the system starts THEN it SHALL perform health checks and report readiness status
4. WHEN errors occur THEN the system SHALL provide comprehensive logging and monitoring capabilities
5. IF dependencies are unavailable THEN the system SHALL fail gracefully with clear error messages

### Requirement 10: Extensible and Open Source

**User Story:** As a developer, I want to extend and customize the system for different Frappe setups, so that it can adapt to various use cases and requirements.

#### Acceptance Criteria

1. WHEN the system is designed THEN it SHALL be Frappe-agnostic and work with any Doctype
2. WHEN developers want to extend functionality THEN the system SHALL provide clear plugin/extension points
3. WHEN the code is released THEN it SHALL be open source with comprehensive documentation
4. WHEN new features are added THEN the system SHALL maintain backward compatibility with existing configurations
5. IF custom processing is needed THEN the system SHALL allow custom chunking and embedding strategies