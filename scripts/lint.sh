#!/bin/bash

# Lint script for both Python and TypeScript code

set -e

echo "🔍 Running Python linting..."

# Run flake8 on backend
echo "Running flake8 on backend..."
cd backend
flake8 . --config=.flake8
cd ..

echo "🔍 Running TypeScript linting..."

# Run ESLint on frontend
echo "Running ESLint on frontend..."
cd frontend
npx eslint . --ext .ts,.tsx
cd ..

echo "✅ All linting checks passed!"