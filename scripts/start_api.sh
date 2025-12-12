#!/bin/bash
set -e

# Test that the app can be imported
echo "Testing app import..."
python -c "import src.api.main; print('✅ App import successful')" || {
    echo "❌ Failed to import app"
    exit 1
}

# Start uvicorn with explicit error handling
echo "Starting uvicorn server..."
# Use exec to replace shell process and ensure proper signal handling
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --log-level info
