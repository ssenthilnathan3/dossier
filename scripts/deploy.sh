#!/bin/bash

# Dossier Production Deployment Script
# This script helps deploy Dossier in production environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
BACKUP_DIR="./backups"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking deployment requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if production compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Production compose file ($COMPOSE_FILE) not found."
        exit 1
    fi
    
    log_success "All requirements met"
}

setup_environment() {
    log_info "Setting up production environment..."
    
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.prod.example" ]; then
            cp .env.prod.example "$ENV_FILE"
            log_warning "Created $ENV_FILE from example. Please configure it before deployment."
            echo "Required configuration:"
            echo "  - POSTGRES_PASSWORD: Secure database password"
            echo "  - FRAPPE_URL: Your Frappe instance URL"
            echo "  - FRAPPE_API_KEY: Frappe API key"
            echo "  - FRAPPE_API_SECRET: Frappe API secret"
            echo "  - WEBHOOK_SECRET: Webhook security secret"
            echo ""
            read -p "Press Enter after configuring $ENV_FILE..."
        else
            log_error "Environment file template not found. Please create $ENV_FILE manually."
            exit 1
        fi
    fi
    
    # Validate required environment variables
    source "$ENV_FILE"
    
    required_vars=("POSTGRES_PASSWORD" "FRAPPE_URL" "FRAPPE_API_KEY" "FRAPPE_API_SECRET" "WEBHOOK_SECRET")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Required environment variable $var is not set in $ENV_FILE"
            exit 1
        fi
    done
    
    log_success "Environment configuration validated"
}

backup_data() {
    log_info "Creating data backup..."
    
    mkdir -p "$BACKUP_DIR"
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="$BACKUP_DIR/dossier_backup_$timestamp.tar.gz"
    
    # Create backup of volumes
    docker run --rm \
        -v dossier_postgres_data:/data/postgres \
        -v dossier_qdrant_data:/data/qdrant \
        -v dossier_redis_data:/data/redis \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine:latest \
        tar czf "/backup/dossier_backup_$timestamp.tar.gz" -C /data .
    
    log_success "Backup created: $backup_file"
}

build_images() {
    log_info "Building production Docker images..."
    
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    log_success "Docker images built successfully"
}

deploy_services() {
    log_info "Deploying services..."
    
    # Pull latest base images
    docker-compose -f "$COMPOSE_FILE" pull redis postgres qdrant ollama
    
    # Start services
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    
    log_success "Services deployed"
}

wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for health checks to pass
    max_attempts=30
    attempt=0
    
    services=("webhook-handler:3001" "ingestion-service:8001" "embedding-service:8002" "query-service:8003" "llm-service:8004")
    
    for service_port in "${services[@]}"; do
        service=$(echo "$service_port" | cut -d: -f1)
        port=$(echo "$service_port" | cut -d: -f2)
        
        log_info "Waiting for $service to be ready..."
        attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            if curl -f -s "http://localhost:$port/health" > /dev/null 2>&1; then
                log_success "$service is ready"
                break
            fi
            
            attempt=$((attempt + 1))
            sleep 5
        done
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "$service failed to become ready within timeout"
            exit 1
        fi
    done
    
    log_success "All services are ready"
}

pull_models() {
    log_info "Pulling LLM models..."
    
    # Wait for Ollama to be ready
    max_attempts=12
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 10
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_warning "Ollama not ready, skipping model pull"
        return
    fi
    
    # Pull default models
    docker-compose -f "$COMPOSE_FILE" exec -T ollama ollama pull llama3.2 || log_warning "Failed to pull llama3.2"
    docker-compose -f "$COMPOSE_FILE" exec -T ollama ollama pull codellama || log_warning "Failed to pull codellama"
    
    log_success "Models pulled successfully"
}

show_status() {
    log_info "Deployment status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    log_info "Service URLs:"
    echo "  Frontend:         http://localhost:3000"
    echo "  Webhook Handler:  http://localhost:3001"
    echo "  Ingestion API:    http://localhost:8001"
    echo "  Embedding API:    http://localhost:8002"
    echo "  Query API:        http://localhost:8003"
    echo "  LLM API:          http://localhost:8004"
    echo "  Qdrant:           http://localhost:6333"
    echo "  Ollama:           http://localhost:11434"
    echo ""
}

cleanup() {
    log_info "Cleaning up deployment..."
    
    docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
    docker system prune -f
    
    log_success "Cleanup completed"
}

# Main deployment function
deploy() {
    log_info "Starting Dossier production deployment..."
    
    check_requirements
    setup_environment
    
    if [ "$1" != "--no-backup" ]; then
        backup_data
    fi
    
    build_images
    deploy_services
    wait_for_services
    pull_models
    show_status
    
    log_success "Deployment completed successfully!"
    log_info "You can now access Dossier at http://localhost:3000"
}

# Command line interface
case "$1" in
    "deploy")
        deploy "$2"
        ;;
    "status")
        show_status
        ;;
    "cleanup")
        cleanup
        ;;
    "backup")
        backup_data
        ;;
    *)
        echo "Usage: $0 {deploy|status|cleanup|backup}"
        echo ""
        echo "Commands:"
        echo "  deploy [--no-backup]  Deploy Dossier in production mode"
        echo "  status                Show deployment status"
        echo "  cleanup               Clean up deployment"
        echo "  backup                Create data backup"
        echo ""
        exit 1
        ;;
esac