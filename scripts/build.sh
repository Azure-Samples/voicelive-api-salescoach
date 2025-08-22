#!/bin/bash

echo "🧹 Cleaning previous build..."
rm -rf frontend/static backend/static frontend/node_modules frontend/package-lock.json

echo "📦 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps

echo "🔨 Building React app..."
npm run build

echo "📋 Copying build to backend static folder..."
cd ..
mkdir -p backend/static
cp -r frontend/static/* backend/static/

echo "✅ Build complete! Run 'cd backend && python src/app.py' to start the server."
