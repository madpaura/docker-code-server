#!/bin/bash

# Build directory
BUILD_DIR="../static/downloads"
mkdir -p "$BUILD_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
if ! command_exists npm; then
    echo "Error: npm is required but not installed."
    exit 1
fi

# Install dependencies
npm install

# Build for each platform
echo "Building Electron apps..."

# Windows build
if command_exists wine; then
    echo "Building Windows executable..."
    npm run build:win
    mv "dist/cxl-qvp Setup 1.0.0.exe" "$BUILD_DIR/cxl-qvp_1.0.0.exe"
else
    echo "Warning: wine not found, skipping Windows build"
fi

# Linux builds
echo "Building Linux packages..."
npm run build:linux
mv "dist/cxl-qvp_1.0.0_amd64.deb" "$BUILD_DIR/cxl-qvp_1.0.0.deb"

echo "Build process completed!"
