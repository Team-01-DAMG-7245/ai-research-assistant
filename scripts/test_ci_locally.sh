#!/bin/bash
# Quick local test script for CI/CD pipeline components

set -e

echo "🧪 Testing CI/CD Pipeline Components Locally"
echo "=" | head -c 60 && echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        return 1
    fi
}

# Check Python versions
echo -e "\n1️⃣ Checking Python versions..."
python3.10 --version 2>/dev/null && print_status 0 "Python 3.10 available" || print_status 1 "Python 3.10 not found"
python3.11 --version 2>/dev/null && print_status 0 "Python 3.11 available" || print_status 1 "Python 3.11 not found"

# Test: Install dependencies and run tests
echo -e "\n2️⃣ Testing test job (Python 3.11)..."
python3.11 -m venv venv-test-311 > /dev/null 2>&1
source venv-test-311/bin/activate
pip install --upgrade pip --quiet > /dev/null 2>&1
pip install -r requirements.txt --quiet > /dev/null 2>&1
pip install pytest pytest-asyncio pytest-cov pytest-mock --quiet > /dev/null 2>&1

APP_ENV=test API_MODE=true pytest tests/ -v --cov=src --cov-report=term-missing > /tmp/test-output.log 2>&1
TEST_RESULT=$?
if [ $TEST_RESULT -eq 0 ]; then
    print_status 0 "Tests passed"
    cat /tmp/test-output.log | tail -5
else
    print_status 1 "Tests failed"
    echo "Last 20 lines of output:"
    tail -20 /tmp/test-output.log
fi
deactivate

# Lint: Check formatting and linting
echo -e "\n3️⃣ Testing lint job..."
python3.11 -m venv venv-lint > /dev/null 2>&1
source venv-lint/bin/activate
pip install --upgrade pip --quiet > /dev/null 2>&1
pip install black isort flake8 pylint --quiet > /dev/null 2>&1

echo "   Checking Black formatting..."
black --check src/ tests/ > /dev/null 2>&1 && print_status 0 "Black formatting OK" || print_status 1 "Black formatting issues (run: black src/ tests/)"

echo "   Checking isort..."
isort --check-only src/ tests/ > /dev/null 2>&1 && print_status 0 "Import sorting OK" || print_status 1 "Import sorting issues (run: isort src/ tests/)"

echo "   Checking flake8..."
flake8 src/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=127 > /dev/null 2>&1 && print_status 0 "flake8 checks OK" || print_status 1 "flake8 found issues"

deactivate

# Docker: Test Docker builds
echo -e "\n4️⃣ Testing Docker builds..."
if command -v docker &> /dev/null; then
    echo "   Building API image..."
    docker build -f Dockerfile.api -t ai-research-assistant-api:test . > /tmp/docker-api.log 2>&1 && \
        print_status 0 "API Docker image built" || print_status 1 "API Docker build failed"
    
    echo "   Building Streamlit image..."
    docker build -f Dockerfile.streamlit -t ai-research-assistant-streamlit:test . > /tmp/docker-streamlit.log 2>&1 && \
        print_status 0 "Streamlit Docker image built" || print_status 1 "Streamlit Docker build failed"
else
    print_status 1 "Docker not found - skipping Docker tests"
fi

# Summary
echo -e "\n" && echo "=" | head -c 60 && echo ""
echo "📊 Test Summary Complete"
echo "=" | head -c 60 && echo ""
echo ""
echo "To test on GitHub, push your changes:"
echo "  git add .github/workflows/ci.yml"
echo "  git commit -m 'Add CI/CD pipeline'"
echo "  git push origin main"
echo ""
echo "Then check the 'Actions' tab on GitHub to see the workflow run."

# Cleanup
rm -rf venv-test-311 venv-lint 2>/dev/null || true



