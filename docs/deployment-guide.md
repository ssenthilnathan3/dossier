# Dossier RAG System - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Dossier RAG system in various environments, from development to production. The system is designed as a microservices architecture with Docker-first deployment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Development Deployment](#development-deployment)
5. [Production Deployment](#production-deployment)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Performance Tuning](#performance-tuning)
9. [Security Considerations](#security-considerations)
10. [Backup and Recovery](#backup-and-recovery)

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 50GB available space
- **Network**: Stable internet connection

#### Recommended Requirements
- **CPU**: 8 cores
- **RAM**: 16GB
- **Storage**: 100GB SSD
- **Network**: High-speed internet connection

### Software Dependencies

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository
- **Make**: For running build scripts (optional)

### External Services

- **Frappe Instance**: Running Frappe/ERPNext instance with webhook capabilities
- **Ollama**: For LLM inference (can be containerized)
- **Domain/SSL**: For production deployments

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/dossier.git
cd dossier
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:

```env
# Database Configuration
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql://dossier:your_secure_password@postgres:5432/dossier

# Frappe Configuration
FRAPPE_URL=https://your-frappe-instance.com
FRAPPE_API_KEY=your_frappe_api_key
FRAPPE_API_SECRET=your_frappe_api_secret

# Security
JWT_SECRET=your_jwt_secret_key
WEBHOOK_SECRET=your_webhook_secret

# LLM Configuration
DEFAULT_MODEL=llama2
OLLAMA_URL=http://ollama:11434

# Optional: External Services
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379
```

### 3. Start the System

```bash
# Development mode
docker-compose up -d

# Production mode
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Verify Deployment

```bash
# Check service health
make health-check

# Or manually check each service
curl http://localhost:8080/health  # API Gateway
curl http://localhost:3001/health  # Webhook Handler
curl http://localhost:8001/health  # Ingestion Service
curl http://localhost:8002/health  # Embedding Service
curl http://localhost:8003/health  # Query Service
curl http://localhost:8004/health  # LLM Service
```

## Configuration

### Environment Variables

#### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` | Yes |
| `FRAPPE_URL` | Frappe instance URL | - | Yes |
| `FRAPPE_API_KEY` | Frappe API key | - | Yes |
| `FRAPPE_API_SECRET` | Frappe API secret | - | Yes |

#### Security Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | JWT signing secret | - | Yes |
| `WEBHOOK_SECRET` | Webhook signature secret | - | Yes |
| `POSTGRES_PASSWORD` | Database password | - | Yes |

#### Service Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEFAULT_MODEL` | Default LLM model | `llama2` | No |
| `OLLAMA_URL` | Ollama service URL | `http://ollama:11434` | No |
| `EMBEDDING_MODEL` | Embedding model name | `all-MiniLM-L6-v2` | No |
| `BATCH_SIZE` | Embedding batch size | `32` | No |

#### Monitoring Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `METRICS_ENABLED` | Enable metrics collection | `true` | No |
| `TRACING_ENABLED` | Enable distributed tracing | `true` | No |

### Service-Specific Configuration

#### API Gateway

```yaml
# docker-compose.override.yml
services:
  api-gateway:
    environment:
      - RATE_LIMIT_REQUESTS=100
      - RATE_LIMIT_WINDOW=60
      - CORS_ORIGINS=*
      - AUTH_ENABLED=true
```

#### Ingestion Service

```yaml
services:
  ingestion-service:
    environment:
      - BATCH_SIZE=10
      - WORKER_CONCURRENCY=4
      - RETRY_MAX_ATTEMPTS=3
      - RETRY_DELAY=5
```

#### Query Service

```yaml
services:
  query-service:
    environment:
      - SEARCH_TIMEOUT=30
      - CACHE_TTL=3600
      - MAX_RESULTS=100
```

#### LLM Service

```yaml
services:
  llm-service:
    environment:
      - RESPONSE_TIMEOUT=60
      - MAX_TOKENS=2048
      - TEMPERATURE=0.7
      - STREAMING_ENABLED=true
```

## Development Deployment

### 1. Development Setup

```bash
# Install development dependencies
make install-dev

# Set up development environment
cp .env.development .env

# Start development services
docker-compose up -d
```

### 2. Development Configuration

```env
# .env.development
NODE_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
METRICS_ENABLED=true
TRACING_ENABLED=true

# Use local Ollama if available
OLLAMA_URL=http://host.docker.internal:11434
```

### 3. Development Tools

```bash
# Run tests
make test

# Run integration tests
make test-integration

# Run end-to-end tests
make test-e2e

# Generate test coverage
make coverage

# Lint code
make lint

# Format code
make format
```

### 4. Hot Reloading

For development, you can enable hot reloading:

```yaml
# docker-compose.override.yml
services:
  frontend:
    volumes:
      - ./services/frontend/src:/app/src
    environment:
      - FAST_REFRESH=true
      
  api-gateway:
    volumes:
      - ./services/api-gateway:/app
    environment:
      - NODE_ENV=development
```

## Production Deployment

### 1. Production Preparation

#### Security Hardening

```bash
# Generate secure secrets
openssl rand -hex 32  # For JWT_SECRET
openssl rand -hex 32  # For WEBHOOK_SECRET
openssl rand -base64 32  # For POSTGRES_PASSWORD
```

#### Resource Planning

```yaml
# docker-compose.prod.yml
services:
  postgres:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
          
  qdrant:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### 2. Production Configuration

```env
# .env.production
NODE_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Security
JWT_SECRET=your_super_secure_jwt_secret
WEBHOOK_SECRET=your_super_secure_webhook_secret
POSTGRES_PASSWORD=your_super_secure_db_password

# Performance
REDIS_MAXMEMORY=2gb
REDIS_MAXMEMORY_POLICY=allkeys-lru

# Monitoring
METRICS_ENABLED=true
TRACING_ENABLED=true
HEALTH_CHECK_INTERVAL=30
```

### 3. SSL/TLS Configuration

#### Using Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/dossier
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Using Traefik

```yaml
# docker-compose.prod.yml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your-email@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - letsencrypt:/letsencrypt
      
  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
```

### 4. Production Deployment Steps

```bash
# 1. Pull latest images
docker-compose -f docker-compose.prod.yml pull

# 2. Build production images
docker-compose -f docker-compose.prod.yml build

# 3. Start services
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify deployment
make health-check-prod

# 5. Run smoke tests
make test-smoke
```

## Monitoring and Maintenance

### 1. Health Monitoring

#### Service Health Checks

```bash
# Check all services
curl http://localhost:8080/health

# Check specific service
curl http://localhost:8001/health

# Check with detailed metrics
curl http://localhost:8080/metrics
```

#### Automated Health Monitoring

```yaml
# docker-compose.prod.yml
services:
  healthcheck:
    image: curlimages/curl:latest
    command: |
      sh -c "
        while true; do
          curl -f http://api-gateway:8080/health || exit 1
          sleep 30
        done
      "
    depends_on:
      - api-gateway
    restart: unless-stopped
```

### 2. Log Management

#### Centralized Logging

```yaml
services:
  fluentd:
    image: fluent/fluentd:latest
    volumes:
      - ./config/fluentd.conf:/fluentd/etc/fluent.conf
    depends_on:
      - elasticsearch
      
  elasticsearch:
    image: elasticsearch:7.17.0
    environment:
      - discovery.type=single-node
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
      
  kibana:
    image: kibana:7.17.0
    depends_on:
      - elasticsearch
    ports:
      - "5601:5601"
```

#### Log Rotation

```bash
# Configure log rotation
cat > /etc/logrotate.d/dossier << EOF
/var/log/dossier/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 root root
}
EOF
```

### 3. Performance Monitoring

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'dossier-services'
    static_configs:
      - targets: ['localhost:8080', 'localhost:8001', 'localhost:8002', 'localhost:8003', 'localhost:8004']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Dossier RAG System",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{service}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### 4. Backup and Recovery

#### Database Backup

```bash
#!/bin/bash
# backup-database.sh

BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="dossier_backup_${TIMESTAMP}.sql"

mkdir -p ${BACKUP_DIR}

docker exec postgres pg_dump -U dossier -d dossier > ${BACKUP_DIR}/${BACKUP_FILE}

# Keep only last 7 days of backups
find ${BACKUP_DIR} -name "*.sql" -mtime +7 -delete

echo "Database backup completed: ${BACKUP_FILE}"
```

#### Vector Database Backup

```bash
#!/bin/bash
# backup-qdrant.sh

BACKUP_DIR="/backups/qdrant"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p ${BACKUP_DIR}

# Create snapshot
curl -X POST "http://localhost:6333/snapshots" \
  -H "Content-Type: application/json" \
  -d '{"name": "backup_'${TIMESTAMP}'"}'

# Download snapshot
curl -X GET "http://localhost:6333/snapshots/backup_${TIMESTAMP}" \
  -o ${BACKUP_DIR}/qdrant_backup_${TIMESTAMP}.snapshot

echo "Qdrant backup completed: qdrant_backup_${TIMESTAMP}.snapshot"
```

#### Automated Backup Schedule

```bash
# Add to crontab
crontab -e

# Daily database backup at 2 AM
0 2 * * * /path/to/backup-database.sh

# Weekly vector database backup on Sunday at 3 AM
0 3 * * 0 /path/to/backup-qdrant.sh
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Check resource usage
docker stats

# Check network connectivity
docker network ls
docker network inspect dossier_default
```

#### 2. Database Connection Issues

```bash
# Check database status
docker exec postgres pg_isready -U dossier

# Check database logs
docker-compose logs postgres

# Test connection
docker exec postgres psql -U dossier -d dossier -c "SELECT 1;"
```

#### 3. High Memory Usage

```bash
# Check memory usage by service
docker stats --no-stream

# Check Qdrant memory usage
curl http://localhost:6333/telemetry

# Check Redis memory usage
docker exec redis redis-cli INFO memory
```

#### 4. Slow Query Performance

```bash
# Check Qdrant performance
curl http://localhost:6333/metrics

# Check database query performance
docker exec postgres psql -U dossier -d dossier -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

### Debug Mode

```bash
# Enable debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG

# Restart services with debug logging
docker-compose down
docker-compose up -d
```

### Performance Diagnostics

```bash
# Run performance benchmarks
make benchmark

# Check system resources
htop
iostat -x 1
netstat -tuln
```

## Performance Tuning

### 1. Database Optimization

```sql
-- PostgreSQL configuration
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET random_page_cost = '1.1';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
SELECT pg_reload_conf();
```

### 2. Vector Database Optimization

```bash
# Qdrant configuration
curl -X PUT "http://localhost:6333/collections/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizers_config": {
      "max_segment_size": 20000,
      "memmap_threshold": 50000,
      "indexing_threshold": 20000
    }
  }'
```

### 3. Caching Strategy

```yaml
# Redis configuration
services:
  redis:
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    environment:
      - REDIS_MAXMEMORY=2gb
      - REDIS_MAXMEMORY_POLICY=allkeys-lru
```

### 4. Load Balancing

```yaml
# Multiple service instances
services:
  query-service:
    deploy:
      replicas: 3
    
  llm-service:
    deploy:
      replicas: 2
```

## Security Considerations

### 1. Network Security

```yaml
# Restrict network access
services:
  postgres:
    networks:
      - database
    # Don't expose ports externally
    
  qdrant:
    networks:
      - vector-db
    # Don't expose ports externally
```

### 2. Authentication and Authorization

```bash
# Implement strong JWT secrets
JWT_SECRET=$(openssl rand -hex 32)

# Use API key authentication for internal services
API_KEY=$(openssl rand -hex 16)
```

### 3. Data Encryption

```yaml
# Enable SSL for database
services:
  postgres:
    environment:
      - POSTGRES_SSL_MODE=require
    volumes:
      - ./certs:/var/lib/postgresql/certs
```

### 4. Security Headers

```nginx
# Nginx security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

## Backup and Recovery

### 1. Recovery Procedures

#### Database Recovery

```bash
# Restore from backup
docker exec -i postgres psql -U dossier -d dossier < /backups/postgres/backup.sql
```

#### Vector Database Recovery

```bash
# Restore Qdrant snapshot
curl -X POST "http://localhost:6333/snapshots/upload" \
  -F "snapshot=@/backups/qdrant/backup.snapshot"
```

### 2. Disaster Recovery Plan

1. **Immediate Response** (0-15 minutes)
   - Assess the situation
   - Stop affected services
   - Preserve logs and data

2. **Short-term Recovery** (15-60 minutes)
   - Restore from backups
   - Verify data integrity
   - Restart services

3. **Long-term Recovery** (1-24 hours)
   - Full system verification
   - Performance testing
   - Documentation updates

### 3. Testing Recovery Procedures

```bash
# Regular recovery tests
make test-recovery

# Simulate failure scenarios
make test-disaster-scenarios
```

## Maintenance Schedule

### Daily Tasks
- [ ] Check service health
- [ ] Review error logs
- [ ] Monitor resource usage
- [ ] Verify backup completion

### Weekly Tasks
- [ ] Update dependencies
- [ ] Run performance benchmarks
- [ ] Review security logs
- [ ] Test backup recovery

### Monthly Tasks
- [ ] Security audit
- [ ] Performance optimization review
- [ ] Documentation updates
- [ ] Disaster recovery test

## Support and Documentation

### Getting Help

- **Documentation**: [GitHub Wiki](https://github.com/your-org/dossier/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-org/dossier/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/dossier/discussions)

### Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on contributing to the project.

### License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.