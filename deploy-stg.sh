#!/bin/bash

# FloodSense - Automated Digital Ocean Staging Deployment Script
# Usage: chmod +x deploy-stg.sh && ./deploy-stg.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log functions
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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    log_success "Docker found: $(docker --version)"
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    log_success "Docker Compose found: $(docker-compose --version)"
    
    if ! command -v git &> /dev/null; then
        log_error "Git not found. Please install Git first."
        exit 1
    fi
    log_success "Git found: $(git --version)"
}

# Verify stg branch
verify_branch() {
    log_info "Verifying branch..."
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    
    if [ "$CURRENT_BRANCH" != "stg" ]; then
        log_warning "Current branch is '$CURRENT_BRANCH', expected 'stg'"
        log_info "Checking out stg branch..."
        git fetch origin
        git checkout stg
        log_success "Switched to stg branch"
    else
        log_success "Already on stg branch"
    fi
    
    # Verify stg is up to date with origin/stg
    git pull origin stg
    log_success "stg branch is up to date"
}

# Check environment file
check_env() {
    log_info "Checking environment configuration..."
    
    if [ ! -f ".env.stg" ]; then
        log_warning ".env.stg not found, creating from template..."
        if [ -f ".env.example" ]; then
            cp .env.example .env.stg
            log_warning "Created .env.stg from .env.example - PLEASE UPDATE WITH PRODUCTION VALUES"
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi
    
    # Check for required variables
    REQUIRED_VARS=("POSTGRES_PASSWORD_STG" "INFLUXDB_PASSWORD_STG" "INFLUXDB_TOKEN_STG")
    
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^${var}=" .env.stg; then
            log_warning "Missing required variable: $var"
        fi
    done
    
    log_success "Environment configuration ready"
}

# Validate docker-compose configuration
validate_compose() {
    log_info "Validating docker-compose configuration..."
    
    if ! docker-compose -f docker-compose.stg.yml config > /dev/null 2>&1; then
        log_error "Docker Compose configuration is invalid"
        exit 1
    fi
    
    log_success "Docker Compose configuration is valid"
}

# Build containers
build_containers() {
    log_info "Building Docker containers..."
    
    if ! docker-compose -f docker-compose.stg.yml build; then
        log_error "Failed to build containers"
        exit 1
    fi
    
    log_success "Containers built successfully"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    if ! docker-compose -f docker-compose.stg.yml up -d; then
        log_error "Failed to start services"
        exit 1
    fi
    
    log_success "Services started"
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    docker-compose -f docker-compose.stg.yml ps
}

# Run migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for database to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    RETRY_COUNT=0
    MAX_RETRIES=30
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if docker-compose -f docker-compose.stg.yml exec -T postgres pg_isready -U flood_stg_user > /dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -n "."
        sleep 2
    done
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "PostgreSQL failed to be ready"
        exit 1
    fi
    
    # Run migrations
    if docker-compose -f docker-compose.stg.yml exec -T api alembic upgrade head; then
        log_success "Database migrations completed"
    else
        log_warning "Database migrations encountered issues - check logs"
    fi
}

# Health check
health_check() {
    log_info "Performing health checks..."
    
    # Check Kong
    if curl -s http://localhost:8001/status > /dev/null 2>&1; then
        log_success "Kong gateway is healthy"
    else
        log_warning "Kong gateway health check failed"
    fi
    
    # Check services
    SERVICES=("api" "postgres" "influxdb" "kafka")
    
    for service in "${SERVICES[@]}"; do
        if docker-compose -f docker-compose.stg.yml exec -T "$service" echo "OK" > /dev/null 2>&1; then
            log_success "$service is running"
        else
            log_warning "$service health check failed"
        fi
    done
}

# Summary
print_summary() {
    log_info "========================================="
    log_success "Deployment completed successfully!"
    log_info "========================================="
    
    echo ""
    echo "Service Status:"
    docker-compose -f docker-compose.stg.yml ps
    
    echo ""
    echo "Next steps:"
    echo "  1. Verify services: docker-compose -f docker-compose.stg.yml logs -f"
    echo "  2. Test API: curl http://localhost:8000/health"
    echo "  3. Configure Nginx reverse proxy (see DIGITAL_OCEAN_DEPLOYMENT.md)"
    echo "  4. Setup SSL certificate with Let's Encrypt"
    echo ""
}

# Cleanup on error
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "Deployment failed!"
        log_info "Stopping services..."
        docker-compose -f docker-compose.stg.yml down
        exit 1
    fi
}

trap cleanup EXIT

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║    FloodSense - Digital Ocean Staging Deployment Script    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    verify_branch
    check_env
    validate_compose
    build_containers
    start_services
    run_migrations
    health_check
    print_summary
}

# Run main
main
