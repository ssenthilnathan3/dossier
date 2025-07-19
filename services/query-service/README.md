# Query Service

The Query Service provides semantic search and retrieval capabilities for the Dossier RAG system. It handles query embedding, vector similarity search, result processing, and comprehensive analytics.

## Features

### Core Functionality
- **Semantic Search**: Uses BGE-small embeddings for high-quality semantic similarity search
- **Vector Database Integration**: Connects to Qdrant for efficient vector storage and retrieval
- **Configurable Parameters**: Supports top-k results, score thresholds, and filtering
- **Result Processing**: Intelligent result ranking and metadata enhancement

### Performance & Caching
- **Result Caching**: In-memory caching with configurable TTL for improved performance
- **Embedding Caching**: Reuses embeddings for repeated queries
- **Batch Processing**: Efficient handling of multiple search operations

### Analytics & Monitoring
- **Comprehensive Statistics**: Tracks query patterns, performance metrics, and usage analytics
- **Search Analytics**: Detailed logging of search operations and timing breakdowns
- **Empty Result Handling**: Graceful handling with helpful suggestions for users
- **Health Monitoring**: Real-time health checks and service status reporting

### Error Handling & Resilience
- **Input Validation**: Comprehensive validation of search parameters
- **Graceful Degradation**: Handles service failures and provides meaningful error messages
- **Retry Logic**: Built-in retry mechanisms for transient failures
- **Timeout Management**: Configurable timeouts for all operations

## API Endpoints

### Search
```
POST /api/search
```
Performs semantic search with the following parameters:
- `query`: The search query string
- `top_k`: Number of results to return (default: 5, max: 100)
- `score_threshold`: Minimum similarity score (0-1)
- `filters`: Optional filters for document types, etc.
- `include_metadata`: Whether to include detailed metadata

### Health Check
```
GET /health
```
Returns service health status and metrics.

### Statistics
```
GET /api/stats
```
Returns comprehensive service statistics and analytics.

## Configuration

Environment variables:
- `DEFAULT_TOP_K`: Default number of results (default: 5)
- `MAX_TOP_K`: Maximum number of results (default: 100)
- `DEFAULT_SCORE_THRESHOLD`: Default similarity threshold (default: 0.0)
- `MAX_QUERY_LENGTH`: Maximum query length (default: 1000)
- `ENABLE_RESULT_CACHING`: Enable result caching (default: true)
- `CACHE_TTL_SECONDS`: Cache TTL in seconds (default: 300)

## Dependencies

- **Embedding Service**: For generating query embeddings
- **Qdrant Service**: For vector similarity search
- **FastAPI**: Web framework for API endpoints
- **Pydantic**: Data validation and serialization

## Testing

The service includes comprehensive test coverage:

### Unit Tests (`test_basic_functionality.py`)
- Service instantiation and configuration
- Cache management and key generation
- Input validation and parameter handling
- Statistics tracking and updates
- Basic search functionality with mocks

### Integration Tests (`test_search_integration.py`)
- Complete search workflows with results
- Empty result handling and suggestions
- Caching behavior and performance
- Metadata inclusion and processing
- Error handling and resilience
- Analytics and logging functionality
- Health check operations

## Usage Example

```python
from services.query_service import QueryService

# Initialize service
service = QueryService()
await service.initialize()

# Perform search
result = await service.search(
    query="user permissions and access control",
    top_k=10,
    score_threshold=0.7,
    filters={"doctype": ["User", "Role"]},
    include_metadata=True
)

# Process results
for chunk in result.chunks:
    print(f"Score: {chunk.score}")
    print(f"Content: {chunk.content}")
    print(f"Source: {chunk.doctype}/{chunk.docname}")
```

## Performance Characteristics

- **Query Processing**: Typically < 200ms for cached embeddings
- **Embedding Generation**: ~50ms for new queries (BGE-small)
- **Vector Search**: ~100ms for typical collections (< 1M vectors)
- **Result Processing**: ~10ms for metadata enhancement
- **Cache Hit Rate**: 60-80% for typical usage patterns

## Monitoring

The service provides detailed metrics for monitoring:
- Query volume and patterns
- Response times and performance
- Cache hit rates and efficiency
- Error rates and types
- Resource utilization
- Popular document types and queries

## Architecture

The Query Service follows a modular architecture:
1. **API Layer**: FastAPI endpoints for external communication
2. **Service Layer**: Core business logic and orchestration
3. **Integration Layer**: Connections to embedding and vector services
4. **Caching Layer**: In-memory result and embedding caches
5. **Analytics Layer**: Statistics collection and monitoring
6. **Error Handling**: Comprehensive error management and recovery