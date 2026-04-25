<#
.SYNOPSIS
    Build Docker image for XMN Exam System Backend

.DESCRIPTION
    This script builds a Docker image for the XMN Exam System Backend service.
    Optionally, it can also run the container after building.

.PARAMETER Run
    If specified, runs the container after building the image.

.PARAMETER Tag
    Specifies the image tag. Default is "xmn-exam-backend:latest".

.PARAMETER Port
    Specifies the host port to map to container port 8000. Default is 8000.

.EXAMPLE
    .\build-docker.ps1
    Builds the Docker image only.

.EXAMPLE
    .\build-docker.ps1 -Run
    Builds the Docker image and runs the container.

.EXAMPLE
    .\build-docker.ps1 -Tag "my-backend:v1.0" -Port 8080 -Run
    Builds with custom tag and port, then runs the container.
#>

[CmdletBinding()]
param(
    [switch]$Run,
    [string]$Tag = "xmn-exam-backend:latest",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

Write-Info "Starting Docker build process..."
Write-Info "Image tag: $Tag"

# Check if Docker is installed
Write-Info "Checking Docker installation..."
try {
    $dockerVersion = docker --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed"
    }
    Write-Info "Docker found: $dockerVersion"
} catch {
    Write-Error "Docker is not installed or not in PATH. Please install Docker first."
    exit 1
}

# Check if Docker daemon is running
Write-Info "Checking Docker daemon..."
try {
    $null = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon not accessible"
    }
    Write-Info "Docker daemon is running"
} catch {
    Write-Error "Docker daemon is not running. Please start Docker first."
    exit 1
}

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Info "Project root: $ProjectRoot"

# Change to project root
Push-Location $ProjectRoot

try {
    # Build Docker image
    Write-Info "Building Docker image..."
    docker build -t $Tag .

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed!"
        exit 1
    }

    Write-Success "Docker image built successfully: $Tag"

    # Run container if requested
    if ($Run) {
        Write-Info "Starting container..."
        Write-Info "Port mapping: host:$Port -> container:8000"

        # Check if port is already in use
        $portInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($portInUse) {
            Write-Error "Port $Port is already in use. Please specify a different port with -Port parameter."
            exit 1
        }

        # Run container
        docker run -d `
            --name xmn-exam-backend `
            -p ${Port}:8000 `
            -v "${ProjectRoot}/data:/app/data" `
            --restart unless-stopped `
            $Tag

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to start container!"
            exit 1
        }

        Write-Success "Container started successfully!"
        Write-Info "API available at: http://localhost:$Port"
        Write-Info "API documentation: http://localhost:$Port/docs"
        Write-Info ""
        Write-Info "Useful commands:"
        Write-Info "  docker logs xmn-exam-backend    - View container logs"
        Write-Info "  docker stop xmn-exam-backend    - Stop container"
        Write-Info "  docker rm xmn-exam-backend      - Remove container"
    } else {
        Write-Info ""
        Write-Info "To run the container, use:"
        Write-Info "  .\scripts\build-docker.ps1 -Run"
        Write-Info ""
        Write-Info "Or manually run:"
        Write-Info "  docker run -d -p ${Port}:8000 --name xmn-exam-backend $Tag"
    }

} finally {
    Pop-Location
}

Write-Success "Done!"
