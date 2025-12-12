#!/bin/bash

# Start Airflow Script
# This script initializes and starts Apache Airflow services

set -e

echo "=========================================="
echo "Starting Apache Airflow for AI Research Assistant"
echo "=========================================="

# Check if .env.airflow exists
if [ ! -f .env.airflow ]; then
    echo "ERROR: .env.airflow file not found!"
    echo "Please create .env.airflow with required environment variables."
    echo "See .env.airflow.example for reference."
    exit 1
fi

# Load environment variables
export $(cat .env.airflow | grep -v '^#' | xargs)

# Set Airflow UID if not set (Linux only)
if [ -z "$AIRFLOW_UID" ]; then
    export AIRFLOW_UID=$(id -u)
    echo "Set AIRFLOW_UID to: $AIRFLOW_UID"
fi

# Create necessary directories
echo "Creating Airflow directories..."
mkdir -p airflow/dags
mkdir -p airflow/logs
mkdir -p airflow/plugins
mkdir -p airflow/config
mkdir -p data

# Generate Fernet key if not set
if [ -z "$AIRFLOW__CORE__FERNET_KEY" ]; then
    echo "Generating Fernet key..."
    FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    echo "AIRFLOW__CORE__FERNET_KEY=$FERNET_KEY" >> .env.airflow
    export AIRFLOW__CORE__FERNET_KEY=$FERNET_KEY
fi

# Generate secret key if using default
if [ "$AIRFLOW__WEBSERVER__SECRET_KEY" = "your-secret-key-change-this-in-production" ]; then
    echo "Generating secret key..."
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/AIRFLOW__WEBSERVER__SECRET_KEY=.*/AIRFLOW__WEBSERVER__SECRET_KEY=$SECRET_KEY/" .env.airflow
    export AIRFLOW__WEBSERVER__SECRET_KEY=$SECRET_KEY
fi

echo ""
echo "=========================================="
echo "Starting Airflow with Docker Compose"
echo "=========================================="
echo ""
echo "This will:"
echo "  1. Initialize the Airflow database"
echo "  2. Create an admin user (username: airflow, password: airflow)"
echo "  3. Start the webserver on http://localhost:8080"
echo "  4. Start the scheduler"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start services with docker-compose
docker-compose -f docker-compose.airflow.yml --env-file .env.airflow up -d

echo ""
echo "=========================================="
echo "Waiting for services to be ready..."
echo "=========================================="

# Wait for webserver to be healthy
echo "Waiting for Airflow webserver..."
timeout=120
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "✓ Airflow webserver is ready!"
        break
    fi
    echo "  Waiting... ($elapsed/$timeout seconds)"
    sleep 5
    elapsed=$((elapsed + 5))
done

if [ $elapsed -ge $timeout ]; then
    echo "ERROR: Airflow webserver did not become ready in time"
    echo "Check logs with: docker-compose -f docker-compose.airflow.yml logs"
    exit 1
fi

echo ""
echo "=========================================="
echo "Airflow is ready!"
echo "=========================================="
echo ""
echo "Access the Airflow UI at:"
echo "  URL:      http://localhost:8080"
echo "  Username: airflow"
echo "  Password: airflow"
echo ""
echo "Useful commands:"
echo "  View logs:    docker-compose -f docker-compose.airflow.yml logs -f"
echo "  Stop:         docker-compose -f docker-compose.airflow.yml down"
echo "  Restart:      docker-compose -f docker-compose.airflow.yml restart"
echo "  Clean reset:  docker-compose -f docker-compose.airflow.yml down -v"
echo ""
echo "To view DAGs, go to: http://localhost:8080/admin/airflow/graph"
echo ""
