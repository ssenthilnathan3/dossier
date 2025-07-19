# Dossier - Live RAG System for Frappe

A production-ready, open-source Live RAG (Retrieval-Augmented Generation) system designed specifically for Frappe documents. Dossier provides real-time document ingestion, intelligent chunking, semantic search, and natural language Q&A capabilities through a modern chat interface.

## 🚀 Features

- **Live Document Synchronization**: Real-time webhook processing for automatic document ingestion
- **Intelligent Text Chunking**: Semantic-aware document splitting with configurable overlap
- **Lightweight Vector Embeddings**: High-quality embeddings using BGE-small model
- **Contextual Search**: Semantic similarity search with metadata filtering
- **Natural Language Q&A**: AI-powered responses using local LLM inference
- **Modern Chat Interface**: Real-time streaming responses with source highlighting
- **Production-Ready**: Docker-first deployment with comprehensive monitoring
- **Extensible Architecture**: Frappe-agnostic design for any document type

## 🏗️ Architecture

Dossier is built as a microservices architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frappe CRM    │────│ Webhook Handler │────│  Message Queue  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  React Frontend │────│   API Gateway   │    │ Ingestion Svc   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Query Service │────│   LLM Service   │    │ Embedding Svc   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │   Qdrant VDB    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Services

- **Webhook Handler** (Node.js): Receives and validates Frappe webhooks
- **Ingestion Service** (Python): Processes documents and manages ingestion workflows
- **Embedding Service** (Python): Generates vector embeddings using BGE-small model
- **Query Service** (Python): Handles semantic search and retrieval
- **LLM Service** (Python): Generates natural language responses using Ollama
- **API Gateway** (Python): Authentication, rate limiting, and request routing
- **Frontend** (React): Modern chat interface with real-time streaming

### Infrastructure

- **PostgreSQL**: Configuration and metadata storage
- **Redis**: Message queuing and caching
- **Qdrant**: Vector database for semantic search
- **Ollama**: Local LLM inference engine

## 🚦 Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 50GB free disk space

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/dossier.git
cd dossier

# Copy and edit environment configuration
cp .env.example .env
# Edit .env with your Frappe instance details
```

### 2. Start the System

```bash
# Start all services
make up

# Wait for services to be ready
make health-check

# Pull LLM models (optional - takes time)
make pull-models
```

### 3. Access the Interface

- **Chat Interface**: http://localhost:3000
- **API Gateway**: http://localhost:8080
- **Service Health**: http://localhost:8080/health

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Database Configuration
DATABASE_URL=postgresql://dossier:your_password@postgres:5432/dossier
REDIS_URL=redis://redis:6379

# Frappe Integration
FRAPPE_URL=https://your-frappe-instance.com
FRAPPE_API_KEY=your_frappe_api_key
FRAPPE_API_SECRET=your_frappe_api_secret

# Security
JWT_SECRET=your_jwt_secret_key
WEBHOOK_SECRET=your_webhook_secret

# LLM Configuration
DEFAULT_MODEL=llama3.2
OLLAMA_URL=http://ollama:11434

# Embedding Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
BATCH_SIZE=32
```

### Doctype Configuration

Configure which Frappe doctypes to index:

```bash
# Access the database
make db-shell

# Insert doctype configuration
INSERT INTO doctype_configs (doctype, enabled, fields, filters, chunk_size, chunk_overlap)
VALUES ('Customer', true, '["customer_name", "customer_details"]', '{"disabled": 0}', 1000, 200);
```

## 📊 Monitoring and Observability

### Health Checks

```bash
# Check all services
make health-check

# Check specific service
curl http://localhost:8001/health

# View service logs
make logs
```

### Metrics and Monitoring

- **Prometheus Metrics**: Available at `/metrics` endpoint on each service
- **Structured Logging**: JSON logs with correlation IDs
- **Distributed Tracing**: Request flow tracking across services

### Performance Monitoring

```bash
# Run performance benchmarks
make benchmark

# View system metrics
make metrics
```

## 🧪 Testing

### Test Suites

```bash
# Run all tests
make test-all

# Run specific test suites
make test-e2e              # End-to-end functionality
make test-performance      # Performance benchmarks
make test-integration      # System integration

# Run deployment validation
python scripts/deployment-validation.py
```

### Integration Testing

```bash
# Test complete workflow
make integration-full

# Test individual components
make test-webhook
make test-ingestion
make test-query
```

## 🚀 Production Deployment

### 1. Production Setup

```bash
# Create production environment
make prod-setup

# Edit production configuration
nano .env.prod
```

### 2. Security Hardening

```bash
# Generate secure secrets
openssl rand -hex 32  # JWT_SECRET
openssl rand -hex 32  # WEBHOOK_SECRET
openssl rand -base64 32  # POSTGRES_PASSWORD
```

### 3. Deploy to Production

```bash
# Build production images
make prod-build

# Start production services
make prod-up

# Verify deployment
make prod-status
make health-check-prod
```

### 4. SSL/TLS Configuration

Configure reverse proxy (Nginx/Traefik) for SSL termination. See [Deployment Guide](docs/deployment-guide.md) for detailed instructions.

## 🛠️ Development

### Development Environment

```bash
# Set up development environment
make setup-dev

# Start development services with hot reload
make dev-up

# Run development tools
make lint
make format
make test
```

### Adding New Features

1. **Service Extensions**: Add new endpoints to existing services
2. **Custom Processors**: Implement custom chunking or embedding strategies
3. **UI Components**: Extend the React frontend with new features
4. **Monitoring**: Add custom metrics and dashboards

### API Documentation

Each service exposes OpenAPI documentation:

- **API Gateway**: http://localhost:8080/docs
- **Ingestion Service**: http://localhost:8001/docs
- **Query Service**: http://localhost:8003/docs
- **LLM Service**: http://localhost:8004/docs

## 📚 Documentation

- **[Deployment Guide](docs/deployment-guide.md)**: Comprehensive deployment instructions
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Configuration Guide](docs/configuration.md)**: Detailed configuration options
- **[Development Guide](docs/development.md)**: Development setup and workflows

## 🔧 Troubleshooting

### Common Issues

1. **Services Won't Start**
   ```bash
   # Check logs
   make logs

   # Check resource usage
   docker stats
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connectivity
   make db-shell

   # Check database logs
   docker-compose logs postgres
   ```

3. **High Memory Usage**
   ```bash
   # Check memory usage
   docker stats --no-stream

   # Restart services
   make restart
   ```

### Debug Mode

```bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG

# Restart services
make restart
```

## 🤝 Contributing

You are welcome to contribute!

### Development Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

- **Documentation**: [GitHub Wiki](https://github.com/your-org/dossier/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-org/dossier/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/dossier/discussions)

## 🙏 Acknowledgments

- [Frappe Framework](https://frappeframework.com/) for the excellent base platform
- [Qdrant](https://qdrant.tech/) for the vector database
- [Ollama](https://ollama.ai/) for local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) for the API framework
- [React](https://reactjs.org/) for the frontend framework

---

**Built with ❤️ for the Frappe community**

For detailed deployment instructions, see the [Deployment Guide](docs/deployment-guide.md).
