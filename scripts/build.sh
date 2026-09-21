#!/bin/bash
set -euo pipefail

echo "🧹 Cleaning previous build..."
rm -rf frontend/static backend/static

echo "📦 Installing frontend dependencies..."
cd frontend
npm ci --legacy-peer-deps

echo "🔨 Building React app..."
npm run build

echo "📋 Copying build to backend static folder..."
cd ..
mkdir -p backend/static
cp -r frontend/static/* backend/static/

echo "✅ Build complete! Run 'cd backend && python src/app.py' to start the server."
