# Docker Deployment Guide

This guide explains how to dockerize and deploy the AI Research Assistant on EC2.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- AWS EC2 instance with Docker installed
- Environment variables configured (see `.env.example`)

## Quick Start

### 1. Build and Run Locally

**Simple Commands (No Profiles Needed):**

All services are built together, but you can selectively start only what you need.

**Build Everything (including Airflow):**
```bash
docker compose build
```

**Start Only API + Streamlit (EC2/Production):**
```bash
docker compose up -d api streamlit
```

**Start Everything (including Airflow):**
```bash
docker compose up -d
```

**Common Commands:**
```bash
# Build all services
docker compose build

# Start only API and Streamlit (recommended for EC2)
docker compose up -d api streamlit

# Start everything including Airflow
docker compose up -d

# View logs for API and Streamlit
docker compose logs -f api streamlit

# View all logs
docker compose logs -f

# Stop all services
docker compose down
```

### 2. Production Deployment

**EC2 / Production (API + Streamlit only):**
```bash
# Build all services (including Airflow images for future use)
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start only API and Streamlit in production mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api streamlit

# View logs
docker compose logs -f api streamlit
```

**With Airflow (all services):**
```bash
# Build all services for production
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start everything including Airflow
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f
```

**Note:** Building with `docker compose build` creates all images (including Airflow), but you can selectively start only the services you need. This is perfect for EC2 where you want all images built but only run API and Streamlit to save resources.

## Services

### API Service (Port 8000)
- FastAPI backend
- REST API endpoints
- Background task processing
- Health check: `http://localhost:8000/health`

### Streamlit Service (Port 8501)
- Web interface
- Connects to API service
- Cost dashboard
- Health check: `http://localhost:8501/_stcore/health`

### Airflow Services
- **Airflow Webserver** (Port 8080): Web UI for monitoring and managing DAGs
  - Access at: `http://localhost:8080`
  - Default credentials: `airflow` / `airflow`
- **Airflow Scheduler**: Executes scheduled DAGs
- **Airflow Postgres**: Metadata database for Airflow
- **Airflow Init**: Initialization container (runs once)

The Airflow setup orchestrates the data ingestion pipeline:
1. **ingest_arxiv_papers**: Fetches papers from arXiv and uploads to S3
2. **process_pdfs**: Processes PDFs into text chunks
3. **generate_embeddings**: Creates embeddings and uploads to Pinecone

Default schedule: Daily at 2 AM UTC (configurable in DAG)

## Environment Variables

Create a `.env` file in the project root with:

```bash
# OpenAI
OPENAI_API_KEY=your_key_here

# Pinecone
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=your_index_name

# AWS
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
S3_BUCKET_NAME=your_bucket_name
AWS_REGION=us-east-1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Database
TASK_DB_PATH=/app/data/tasks.db
```

## EC2 Deployment Steps

### 1. Prepare EC2 Instance

```bash
# SSH into EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Install Docker
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose V2 (plugin, comes with Docker Desktop or can be installed separately)
# For Linux, Docker Compose V2 is included with Docker Engine 20.10+
# Verify installation:
docker compose version

# Log out and back in for group changes to take effect
exit
```

### 2. Transfer Files to EC2

```bash
# From your local machine
scp -i your-key.pem -r . ec2-user@your-ec2-ip:/home/ec2-user/ai-research-assistant/

# Or use git
ssh -i your-key.pem ec2-user@your-ec2-ip
git clone your-repo-url
cd ai-research-assistant
```

### 3. Configure Environment

```bash
# On EC2 instance
cd /home/ec2-user/ai-research-assistant
cp .env.example .env
nano .env  # Edit with your API keys
```

### 4. Build and Deploy

**Without Airflow (API + Streamlit only):**
```bash
# Build images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker compose ps
docker compose logs -f
```

**With Airflow (all services):**
```bash
# Build images (all services)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile airflow build

# Start services (all services)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile airflow up -d

# Check status
docker compose ps
docker compose logs -f
```

### 5. Configure Security Groups

In AWS Console, configure EC2 Security Group to allow:
- Port 8000 (API) - from your IP or load balancer
- Port 8501 (Streamlit) - from your IP or load balancer
- Port 8080 (Airflow) - from your IP only (recommended: restrict access)
- Port 22 (SSH) - from your IP only

### 6. Set Up Reverse Proxy (Optional but Recommended)

Using Nginx:

```bash
# Install Nginx
sudo yum install nginx -y

# Create Nginx config
sudo nano /etc/nginx/conf.d/ai-research.conf
```

Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Streamlit
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

## Maintenance

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f streamlit
docker compose logs -f airflow-webserver
docker compose logs -f airflow-scheduler
```

### Airflow Management

```bash
# Access Airflow Web UI
# Open browser: http://localhost:8080
# Login: airflow / airflow

# View DAGs
docker compose exec airflow-webserver airflow dags list

# Trigger a DAG manually
docker compose exec airflow-webserver airflow dags trigger arxiv_daily_ingestion

# Pause/Unpause a DAG
docker compose exec airflow-webserver airflow dags pause arxiv_daily_ingestion
docker compose exec airflow-webserver airflow dags unpause arxiv_daily_ingestion

# View task logs
docker compose exec airflow-webserver airflow tasks logs arxiv_daily_ingestion ingest_arxiv_papers
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart api
```

### Update Application

**Without Airflow:**
```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**With Airflow:**
```bash
# Pull latest code
git pull

# Rebuild and restart (all services)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile airflow up -d --build
```

### Backup Data

```bash
# Backup database and logs
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/

# Restore
tar -xzf backup-YYYYMMDD.tar.gz
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose logs

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|8501'

# Check Docker status
docker ps -a
docker compose ps
```

### API not accessible

```bash
# Check API health
curl http://localhost:8000/health

# Check if container is running
docker compose ps api

# Check API logs
docker compose logs api
```

### Streamlit can't connect to API

```bash
# Verify API_BASE_URL in docker-compose.yml
# Should be: http://api:8000 (internal Docker network)

# Test connectivity from Streamlit container
docker compose exec streamlit curl http://api:8000/health
```

### Out of memory

```bash
# Check resource usage
docker stats

# Adjust limits in docker-compose.prod.yml
# Or use smaller worker count
```

## Production Best Practices

1. **Use HTTPS**: Set up SSL/TLS with Let's Encrypt
2. **Monitor Resources**: Use CloudWatch or similar
3. **Backup Regularly**: Automate database backups
4. **Log Rotation**: Configure log rotation in docker-compose.prod.yml
5. **Security Updates**: Keep Docker and images updated
6. **Resource Limits**: Set appropriate CPU/memory limits
7. **Health Checks**: Monitor health endpoints
8. **Load Balancing**: Use ALB for multiple instances

## Scaling

For high traffic, consider:
- Multiple API instances behind a load balancer
- Separate database (PostgreSQL instead of SQLite)
- Redis for task queue
- Separate Streamlit instances

## Cost Optimization

- Use EC2 Spot Instances for development
- Right-size instance types
- Use CloudWatch for monitoring
- Set up auto-scaling if needed

## Airflow Configuration

### Changing DAG Schedule

Edit `dags/arxiv_ingestion_dag.py` to modify the schedule:

```python
dag = DAG(
    'arxiv_daily_ingestion',
    schedule_interval='0 2 * * *',  # Daily at 2 AM UTC
    # Options:
    # '0 2 * * *' - Daily at 2 AM
    # '0 2 * * 0' - Weekly on Sunday at 2 AM
    # '@daily' - Once per day
    # '@weekly' - Once per week
    # None - Manual trigger only
)
```

### Adjusting Paper Count

Modify the `max_papers` parameter in the DAG:

```python
ingest_papers = PythonOperator(
    task_id='ingest_arxiv_papers',
    python_callable=run_ingestion_task,
    op_kwargs={
        'max_papers': 100,  # Change this value
        'categories': ['cs.AI', 'cs.LG', 'cs.CL'],
    },
)
```

### Airflow Credentials

Default credentials are `airflow` / `airflow`. To change:

1. Set environment variables in docker-compose.yml:
```yaml
environment:
  - _AIRFLOW_WWW_USER_USERNAME=your_username
  - _AIRFLOW_WWW_USER_PASSWORD=your_password
```

2. Or use Airflow CLI:
```bash
docker compose exec airflow-webserver airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password your_password
```

### Incremental Ingestion (Future Enhancement)

To implement incremental ingestion (only fetch new papers):
1. Track last ingestion timestamp in S3 or database
2. Modify `run_ingestion_task` to filter papers by date
3. Update DAG to pass last run timestamp to task
