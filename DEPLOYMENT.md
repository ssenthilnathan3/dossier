# Dossier RAG System - Complete Deployment Guide

## 🚀 Complete Deployment Steps

This guide provides step-by-step instructions for deploying the Dossier RAG system from development to production.

### Phase 1: Pre-Deployment Setup

#### 1. System Requirements Check
```bash
# Verify system requirements
python scripts/deployment-validation.py

# Check minimum requirements:
# - CPU: 4+ cores (8+ recommended)
# - RAM: 8GB+ (16GB+ recommended)  
# - Storage: 50GB+ free space
# - Docker 20.10+ and Docker Compose 2.0+
```

#### 2. Clone and Setup Repository
```bash
# Clone the repository
git clone https://github.com/your-org/dossier.git
cd dossier

# Verify project structure
ls -la
```

#### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration file
nano .env
```

**Required Environment Variables:**
```env
# Database Configuration
DATABASE_URL=postgresql://dossier:YOUR_SECURE_PASSWORD@postgres:5432/dossier
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Frappe Integration (REQUIRED)
FRAPPE_URL=https://your-frappe-instance.com
FRAPPE_API_KEY=your_frappe_api_key
FRAPPE_API_SECRET=your_frappe_api_secret

# Security (Generate secure secrets)
JWT_SECRET=your_jwt_secret_32_chars_minimum
WEBHOOK_SECRET=your_webhook_secret_16_chars_minimum

# LLM Configuration
DEFAULT_MODEL=llama3.2
OLLAMA_URL=http://ollama:11434

# Services Configuration
REDIS_URL=redis://redis:6379
QDRANT_URL=http://qdrant:6333
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

#### 4. Generate Secure Secrets
```bash
# Generate JWT secret (32+ characters)
openssl rand -hex 32

# Generate webhook secret (16+ characters) 
openssl rand -hex 16

# Generate database password
openssl rand -base64 32
```

### Phase 2: Development Deployment

#### 5. Quick Development Setup
```bash
# Complete development setup (recommended for first-time)
make quick-start

# This will:
# - Build all Docker images
# - Start all services
# - Set up database schema
# - Initialize vector collections
# - Run integration tests
```

#### 6. Manual Development Setup (Alternative)
```bash
# Build all services
make build

# Start all services
make up

# Wait for services to be ready
make health-check

# Set up system integration
make integration-setup

# Pull LLM models (takes 10-30 minutes)
make pull-models
```

#### 7. Verify Development Deployment
```bash
# Check all services are healthy
make health-check

# Run integration tests
make test-integration

# Run end-to-end tests
make test-e2e

# Access the system:
# - Frontend: http://localhost:3000
# - API Gateway: http://localhost:8080
# - API Docs: http://localhost:8080/docs
```

### Phase 3: Production Deployment

#### 8. Production Environment Setup
```bash
# Create production environment file
make prod-setup

# Edit production configuration
nano .env.prod
```

**Production Environment Variables:**
```env
# Production settings
NODE_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Use strong, unique secrets
JWT_SECRET=your_production_jwt_secret_64_chars
WEBHOOK_SECRET=your_production_webhook_secret_32_chars
POSTGRES_PASSWORD=your_production_db_password

# Production database (consider external PostgreSQL)
DATABASE_URL=postgresql://dossier:prod_password@postgres:5432/dossier

# External services (recommended for production)
REDIS_URL=redis://redis:6379
QDRANT_URL=http://qdrant:6333

# Performance settings
REDIS_MAXMEMORY=2gb
REDIS_MAXMEMORY_POLICY=allkeys-lru
```

#### 9. Production Build and Deploy
```bash
# Build production images
make prod-build

# Start production services
make prod-up

# Verify production deployment
make prod-status
make health-check-prod
```

#### 10. SSL/TLS Setup (Production)

**Option A: Using Nginx Reverse Proxy**
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

**Option B: Using Docker Compose with Traefik**
```yaml
# Add to docker-compose.prod.yml
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
```

### Phase 4: Post-Deployment Configuration

#### 11. Configure Frappe Doctypes
```bash
# Access database
make db-shell

# Configure which doctypes to index
INSERT INTO doctype_configs (doctype, enabled, fields, filters, chunk_size, chunk_overlap)
VALUES 
    ('Customer', true, '["customer_name", "customer_details", "customer_group"]', '{"disabled": 0}', 1000, 200),
    ('Item', true, '["item_name", "description", "item_group"]', '{"disabled": 0}', 800, 150),
    ('Sales Order', true, '["customer", "items", "remarks"]', '{"docstatus": 1}', 1200, 250);
```

#### 12. Set Up Frappe Webhooks
In your Frappe instance:
1. Go to **Setup > Integrations > Webhook**
2. Create a new webhook:
   - **Webhook URL**: `https://your-domain.com/api/webhooks/frappe`
   - **Request Method**: POST
   - **Document Type**: Select your configured doctypes
   - **Webhook Secret**: Use the same secret from your `.env` file

#### 13. Test End-to-End Workflow
```bash
# Test complete system
make test-all

# Test specific workflow
make integration-full

# Performance benchmarks
make benchmark
```

### Phase 5: Monitoring and Maintenance

#### 14. Set Up Monitoring
```bash
# Start monitoring services (if using external monitoring)
# Configure Prometheus to scrape metrics from:
# - http://localhost:8080/metrics (API Gateway)
# - http://localhost:8001/metrics (Ingestion Service)
# - http://localhost:8002/metrics (Embedding Service)
# - http://localhost:8003/metrics (Query Service)
# - http://localhost:8004/metrics (LLM Service)
```

#### 15. Configure Backups
```bash
# Set up automated backups
# Database backup
0 2 * * * /path/to/dossier/scripts/backup-database.sh

# Vector database backup
0 3 * * 0 /path/to/dossier/scripts/backup-qdrant.sh

# Create backup scripts
cat > scripts/backup-database.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p ${BACKUP_DIR}
docker exec postgres pg_dump -U dossier -d dossier > ${BACKUP_DIR}/dossier_backup_${TIMESTAMP}.sql
find ${BACKUP_DIR} -name "*.sql" -mtime +7 -delete
EOF

chmod +x scripts/backup-database.sh
```

#### 16. Health Monitoring Setup
```bash
# Set up health check monitoring
# Add to crontab:
*/5 * * * * /path/to/dossier/scripts/health-monitor.sh

# Create health monitor script
cat > scripts/health-monitor.sh << 'EOF'
#!/bin/bash
if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "ALERT: Dossier system is down!" | mail -s "Dossier Alert" admin@yourcompany.com
fi
EOF

chmod +x scripts/health-monitor.sh
```

### Phase 6: Verification and Testing

#### 17. Final Verification
```bash
# Comprehensive system validation
python scripts/deployment-validation.py

# Performance validation
make benchmark

# Security validation
make validate-security

# Complete system test
make test-all
```

#### 18. User Acceptance Testing
1. **Access the chat interface**: `https://your-domain.com`
2. **Test document search**: Search for known documents
3. **Test Q&A**: Ask questions about your documents
4. **Verify real-time updates**: Create/update documents in Frappe
5. **Test performance**: Multiple concurrent users

### Phase 7: Go-Live

#### 19. Production Checklist
- [ ] All services are healthy
- [ ] SSL certificates are valid
- [ ] Backups are configured
- [ ] Monitoring is active
- [ ] Performance benchmarks pass
- [ ] Security validation complete
- [ ] Documentation is updated
- [ ] Users are trained

#### 20. Launch Commands
```bash
# Final production startup
make prod-up

# Verify everything is working
make health-check-prod
make validate-system

# Monitor logs during launch
make prod-logs
```

## 🎯 Quick Commands Summary

### Development
```bash
make quick-start          # Complete dev setup
make health-check         # Check system health
make test-all            # Run all tests
```

### Production
```bash
make prod-setup          # Create production config
make prod-build          # Build production images
make prod-up             # Start production system
make health-check-prod   # Verify production health
```

### Maintenance
```bash
make backup              # Create backups
make logs               # View logs
make restart            # Restart services
make clean              # Clean up system
```

### Monitoring
```bash
make metrics            # View metrics
make benchmark          # Performance test
make validate-system    # Complete validation
```

## 🔧 Configuration Details

### Environment Variables Reference

#### Core Configuration
| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | Yes |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | Yes |
| `FRAPPE_URL` | Frappe instance URL | `https://your-frappe.com` | Yes |
| `FRAPPE_API_KEY` | Frappe API key | `your_api_key` | Yes |
| `FRAPPE_API_SECRET` | Frappe API secret | `your_api_secret` | Yes |

#### Security Configuration
| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | JWT signing secret | `your_jwt_secret_32_chars` | Yes |
| `WEBHOOK_SECRET` | Webhook signature secret | `your_webhook_secret` | Yes |
| `POSTGRES_PASSWORD` | Database password | `secure_password` | Yes |

#### Service Configuration
| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEFAULT_MODEL` | Default LLM model | `llama3.2` | No |
| `OLLAMA_URL` | Ollama service URL | `http://ollama:11434` | No |
| `EMBEDDING_MODEL` | Embedding model name | `all-MiniLM-L6-v2` | No |
| `BATCH_SIZE` | Embedding batch size | `32` | No |

### Service Ports
| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React chat interface |
| Webhook Handler | 3001 | Frappe webhook receiver |
| Ingestion Service | 8001 | Document processing |
| Embedding Service | 8002 | Vector embedding generation |
| Query Service | 8003 | Search and retrieval |
| LLM Service | 8004 | AI response generation |
| API Gateway | 8080 | Authentication and routing |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Message queue and cache |
| Qdrant | 6333 | Vector database |
| Ollama | 11434 | LLM inference |

## 🆘 Troubleshooting

### Common Issues

#### 1. Services Won't Start
```bash
# Check logs
make logs

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

## 📊 Performance Expectations

### Typical Performance Metrics
- **Query Response Time**: < 2 seconds
- **LLM Response Time**: < 30 seconds
- **Embedding Generation**: 20+ texts/second
- **Concurrent Users**: 50+ users
- **Memory Usage**: < 16GB total
- **Storage Growth**: ~1GB per 10K documents

### Scaling Recommendations
- **Light Load** (< 100 documents): Default configuration
- **Medium Load** (100-10K documents): Increase memory to 16GB
- **Heavy Load** (10K+ documents): Consider horizontal scaling

## 🔐 Security Best Practices

### Production Security Checklist
- [ ] Use strong, unique secrets (32+ characters)
- [ ] Enable SSL/TLS encryption
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Enable request logging
- [ ] Configure CORS properly
- [ ] Use environment variables for secrets
- [ ] Regular security updates

### Security Monitoring
```bash
# Check security configuration
make validate-security

# Monitor failed authentication attempts
make logs | grep "401\|403"

# Review rate limiting logs
make logs | grep "rate limit"
```

## 📚 Additional Resources

### Documentation
- [System Architecture](docs/architecture.md)
- [API Reference](docs/api-reference.md)
- [Configuration Guide](docs/configuration.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

### Support
- **GitHub Issues**: [Report bugs](https://github.com/your-org/dossier/issues)
- **Discussions**: [Community support](https://github.com/your-org/dossier/discussions)
- **Wiki**: [Additional documentation](https://github.com/your-org/dossier/wiki)

### Contributing
- [Development Guide](docs/development.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

---

**Success!** 🎉 Your Dossier RAG system is now ready for production use. The system provides intelligent document search and Q&A capabilities for your Frappe deployment with real-time synchronization and modern chat interface.

For ongoing support and updates, please refer to the project repository and documentation.