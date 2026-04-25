#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
TAG="xmn-exam-backend:latest"
PORT=8000
RUN_CONTAINER=false

# Function to print colored output
print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Build Docker image for XMN Exam System Backend

OPTIONS:
    -r, --run           Run the container after building
    -t, --tag TAG       Specify image tag (default: xmn-exam-backend:latest)
    -p, --port PORT     Specify host port (default: 8000)
    -h, --help          Show this help message

EXAMPLES:
    $(basename "$0")
        Build the Docker image only.

    $(basename "$0") --run
        Build the Docker image and run the container.

    $(basename "$0") -t my-backend:v1.0 -p 8080 --run
        Build with custom tag and port, then run the container.
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--run)
            RUN_CONTAINER=true
            shift
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

print_info "Starting Docker build process..."
print_info "Image tag: $TAG"

# Check if Docker is installed
print_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH. Please install Docker first."
    exit 1
fi
print_info "Docker found: $(docker --version)"

# Check if Docker daemon is running
print_info "Checking Docker daemon..."
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running. Please start Docker first."
    exit 1
fi
print_info "Docker daemon is running"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_info "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# Build Docker image
print_info "Building Docker image..."
if ! docker build -t "$TAG" .; then
    print_error "Docker build failed!"
    exit 1
fi

print_success "Docker image built successfully: $TAG"

# Run container if requested
if [ "$RUN_CONTAINER" = true ]; then
    print_info "Starting container..."
    print_info "Port mapping: host:$PORT -> container:8000"

    # Check if port is already in use
    if command -v lsof &> /dev/null; then
        if lsof -Pi :"$PORT" -sTCP:LISTEN -t &> /dev/null; then
            print_error "Port $PORT is already in use. Please specify a different port with -p option."
            exit 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
            print_error "Port $PORT is already in use. Please specify a different port with -p option."
            exit 1
        fi
    fi

    # Remove existing container if exists
    if docker ps -a --format '{{.Names}}' | grep -q "^xmn-exam-backend$"; then
        print_info "Removing existing container..."
        docker rm -f xmn-exam-backend &> /dev/null
    fi

    # Create data directory if not exists
    mkdir -p "$PROJECT_ROOT/data"

    # Run container
    if ! docker run -d \
        --name xmn-exam-backend \
        -p "$PORT":8000 \
        -v "$PROJECT_ROOT/data:/app/data" \
        --restart unless-stopped \
        "$TAG"; then
        print_error "Failed to start container!"
        exit 1
    fi

    print_success "Container started successfully!"
    print_info "API available at: http://localhost:$PORT"
    print_info "API documentation: http://localhost:$PORT/docs"
    echo ""
    print_info "Useful commands:"
    print_info "  docker logs xmn-exam-backend    - View container logs"
    print_info "  docker stop xmn-exam-backend    - Stop container"
    print_info "  docker rm xmn-exam-backend      - Remove container"
else
    echo ""
    print_info "To run the container, use:"
    print_info "  ./scripts/build-docker.sh --run"
    echo ""
    print_info "Or manually run:"
    print_info "  docker run -d -p $PORT:8000 --name xmn-exam-backend $TAG"
fi

print_success "Done!"
