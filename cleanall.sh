#!/bin/bash

#rm -rf ./.pytest_cache
#rm -rf backend/.pytest_cache
#rm -rf backend/.ruff_cache
#rm -rf backend/.venv
#rm -rf backend/src/__pycache__
#rm -rf backend/src/models/__pycache__
#rm -rf backend/src/routers/__pycache__
#rm -rf backend/src/services/__pycache__
#rm -rf backend/tests/__pycache__
#rm -rf backend/tests/test_files

rm -rf frontend/node_modules
#rm -rf frontend/src/api
#rm -rf src/static/dist/*

echo \\e[32mCleaned all files successfully.\\e[0m
