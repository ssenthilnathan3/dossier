#!/bin/bash

# Dossier Documentation Website Setup Script
# This script sets up the documentation website for local development or deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NODE_MIN_VERSION="18"
DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="dossier-docs"

# Helper functions
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Node.js version
check_node_version() {
    if command_exists node; then
        local node_version=$(node --version | sed 's/v//' | cut -d. -f1)
        if [ "$node_version" -ge "$NODE_MIN_VERSION" ]; then
            print_success "Node.js version $(node --version) is compatible"
            return 0
        else
            print_error "Node.js version $(node --version) is too old. Required: v$NODE_MIN_VERSION+"
            return 1
        fi
    else
        print_error "Node.js is not installed"
        return 1
    fi
}

# Check npm/yarn
check_package_manager() {
    if command_exists npm; then
        PACKAGE_MANAGER="npm"
        print_success "Using npm $(npm --version)"
        return 0
    elif command_exists yarn; then
        PACKAGE_MANAGER="yarn"
        print_success "Using yarn $(yarn --version)"
        return 0
    else
        print_error "Neither npm nor yarn is installed"
        return 1
    fi
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    cd "$DOCS_DIR"

    if [ "$PACKAGE_MANAGER" = "npm" ]; then
        npm install
    else
        yarn install
    fi

    print_success "Dependencies installed successfully"
}

# Setup development environment
setup_dev_environment() {
    print_header "Setting Up Development Environment"

    # Create .env.local if it doesn't exist
    if [ ! -f "$DOCS_DIR/.env.local" ]; then
        cat > "$DOCS_DIR/.env.local" << EOF
# Development environment variables
NODE_ENV=development
NEXT_TELEMETRY_DISABLED=1

# Add your custom environment variables here
# GOOGLE_ANALYTICS_ID=GA_MEASUREMENT_ID
# GITHUB_TOKEN=your_github_token_for_api_access
EOF
        print_success "Created .env.local file"
    else
        print_info ".env.local already exists"
    fi

    # Create .gitignore if it doesn't exist
    if [ ! -f "$DOCS_DIR/.gitignore" ]; then
        cat > "$DOCS_DIR/.gitignore" << EOF
# Dependencies
node_modules/
.pnp
.pnp.js

# Production build
.next/
out/
dist/

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# Debug
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs
*.log

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# Coverage directory used by tools like istanbul
coverage/
*.lcov

# nyc test coverage
.nyc_output

# Dependency directories
node_modules/
jspm_packages/

# Optional npm cache directory
.npm

# Optional eslint cache
.eslintcache

# Microbundle cache
.rpt2_cache/
.rts2_cache_cjs/
.rts2_cache_es/
.rts2_cache_umd/

# Optional REPL history
.node_repl_history

# Output of 'npm pack'
*.tgz

# Yarn Integrity file
.yarn-integrity

# parcel-bundler cache (https://parceljs.org/)
.cache
.parcel-cache

# Next.js build output
.next

# Nuxt.js build / generate output
.nuxt

# Gatsby files
.cache/
public

# Storybook build outputs
.out
.storybook-out

# Temporary folders
tmp/
temp/
EOF
        print_success "Created .gitignore file"
    fi
}

# Build the documentation
build_docs() {
    print_header "Building Documentation"

    cd "$DOCS_DIR"

    if [ "$PACKAGE_MANAGER" = "npm" ]; then
        npm run build
    else
        yarn build
    fi

    print_success "Documentation built successfully"
}

# Export static site
export_static() {
    print_header "Exporting Static Site"

    cd "$DOCS_DIR"

    if [ "$PACKAGE_MANAGER" = "npm" ]; then
        npm run export
    else
        yarn export
    fi

    print_success "Static site exported to 'out' directory"
}

# Start development server
start_dev_server() {
    print_header "Starting Development Server"

    cd "$DOCS_DIR"

    print_info "Starting development server at http://localhost:3000"
    print_info "Press Ctrl+C to stop the server"

    if [ "$PACKAGE_MANAGER" = "npm" ]; then
        npm run dev
    else
        yarn dev
    fi
}

# Validate setup
validate_setup() {
    print_header "Validating Setup"

    # Check if package.json exists
    if [ -f "$DOCS_DIR/package.json" ]; then
        print_success "package.json found"
    else
        print_error "package.json not found"
        return 1
    fi

    # Check if node_modules exists
    if [ -d "$DOCS_DIR/node_modules" ]; then
        print_success "node_modules directory found"
    else
        print_warning "node_modules directory not found - run install first"
    fi

    # Check if critical files exist
    local critical_files=("next.config.js" "theme.config.tsx" "pages/index.mdx")
    for file in "${critical_files[@]}"; do
        if [ -f "$DOCS_DIR/$file" ]; then
            print_success "$file found"
        else
            print_error "$file not found"
            return 1
        fi
    done

    print_success "Setup validation completed"
}

# Deploy to platforms
deploy_vercel() {
    print_header "Deploying to Vercel"

    if ! command_exists vercel; then
        print_info "Installing Vercel CLI..."
        if [ "$PACKAGE_MANAGER" = "npm" ]; then
            npm install -g vercel
        else
            yarn global add vercel
        fi
    fi

    cd "$DOCS_DIR"
    vercel --prod

    print_success "Deployed to Vercel"
}

deploy_netlify() {
    print_header "Deploying to Netlify"

    if ! command_exists netlify; then
        print_info "Installing Netlify CLI..."
        if [ "$PACKAGE_MANAGER" = "npm" ]; then
            npm install -g netlify-cli
        else
            yarn global add netlify-cli
        fi
    fi

    cd "$DOCS_DIR"

    # Build and export first
    build_docs
    export_static

    netlify deploy --prod --dir=out

    print_success "Deployed to Netlify"
}

# Show help
show_help() {
    cat << EOF
Dossier Documentation Website Setup Script

Usage: $0 [COMMAND]

Commands:
    install         Install dependencies
    setup           Setup development environment
    dev             Start development server
    build           Build the documentation
    export          Export static site
    validate        Validate the setup
    deploy-vercel   Deploy to Vercel
    deploy-netlify  Deploy to Netlify
    all             Run complete setup (install + setup + build)
    help            Show this help message

Examples:
    $0 all                  # Complete setup
    $0 dev                  # Start development server
    $0 build && $0 export   # Build and export static site
    $0 deploy-vercel        # Deploy to Vercel

For more information, visit: https://dossier-docs.vercel.app
EOF
}

# Main execution
main() {
    print_header "Dossier Documentation Website Setup"

    # Change to docs directory
    cd "$DOCS_DIR"

    case "${1:-help}" in
        "install")
            check_node_version && check_package_manager && install_dependencies
            ;;
        "setup")
            setup_dev_environment
            ;;
        "dev")
            check_node_version && check_package_manager && start_dev_server
            ;;
        "build")
            check_node_version && check_package_manager && build_docs
            ;;
        "export")
            check_node_version && check_package_manager && export_static
            ;;
        "validate")
            validate_setup
            ;;
        "deploy-vercel")
            check_node_version && check_package_manager && deploy_vercel
            ;;
        "deploy-netlify")
            check_node_version && check_package_manager && deploy_netlify
            ;;
        "all")
            if check_node_version && check_package_manager; then
                install_dependencies
                setup_dev_environment
                build_docs
                validate_setup
                print_success "Complete setup finished!"
                print_info "Run '$0 dev' to start the development server"
                print_info "Run '$0 export' to build static files for deployment"
            fi
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Check if script is being run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
