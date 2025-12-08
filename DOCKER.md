# Docker Deployment Guide

This guide explains how to dockerize and deploy the AI Research Assistant on EC2.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- AWS EC2 instance with Docker installed
- Environment variables configured (see `.env.example`)

## Quick Start

### 1. Build and Run Locally

```bash
# Build 
docker compose build

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### 2. Production Deployment

```bash
# Build for production
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start in production mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f
```

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

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

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

```bash
# Build images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps
docker-compose logs -f
```

### 5. Configure Security Groups

In AWS Console, configure EC2 Security Group to allow:
- Port 8000 (API) - from your IP or load balancer
- Port 8501 (Streamlit) - from your IP or load balancer
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
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f streamlit
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
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
docker-compose logs

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|8501'

# Check Docker status
docker ps -a
docker-compose ps
```

### API not accessible

```bash
# Check API health
curl http://localhost:8000/health

# Check if container is running
docker-compose ps api

# Check API logs
docker-compose logs api
```

### Streamlit can't connect to API

```bash
# Verify API_BASE_URL in docker-compose.yml
# Should be: http://api:8000 (internal Docker network)

# Test connectivity from Streamlit container
docker-compose exec streamlit curl http://api:8000/health
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
