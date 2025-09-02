#!/bin/bash

rm -rf backend/.venv
rm -rf backend/src/__pycache__
rm -rf backend/src/services/__pycache__
rm -rf backend/tests/__pycache__
rm -rf backend/tests/unit/__pycache__

rm -rf frontend/node_modules

echo \\e[32mCleaned all files successfully.\\e[0m
