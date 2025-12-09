# Airflow Setup Guide

This guide explains how to use Apache Airflow for orchestrating the arXiv paper ingestion pipeline.

## Overview

Airflow manages the complete data ingestion workflow:
1. **Ingest**: Fetch papers from arXiv and upload to S3
2. **Process**: Extract text chunks from PDFs
3. **Embed**: Generate embeddings and upload to Pinecone

## Quick Start

### 1. Start Airflow Services

```bash
# Build and start all services (including Airflow)
docker compose up -d

# Wait for Airflow to initialize (first time only, ~1-2 minutes)
docker compose logs -f airflow-init

# Check Airflow webserver is running
curl http://localhost:8080/health
```

### 2. Access Airflow Web UI

1. Open browser: `http://localhost:8080`
2. Login with default credentials:
   - Username: `airflow`
   - Password: `airflow`

### 3. Enable and Monitor DAG

1. In Airflow UI, find the `arxiv_daily_ingestion` DAG
2. Toggle it ON (unpause) using the switch on the left
3. The DAG will run automatically according to schedule (daily at 2 AM UTC)
4. Or trigger manually: Click DAG → "Trigger DAG"

## DAG Structure

```
arxiv_daily_ingestion
├── check_dependencies (verifies env vars and imports)
├── ingest_arxiv_papers (fetches papers from arXiv)
├── process_pdfs (processes PDFs into chunks)
└── generate_embeddings (creates embeddings for Pinecone)
```

## Configuration

### Schedule

Default: Daily at 2 AM UTC (`0 2 * * *`)

To change, edit `dags/arxiv_ingestion_dag.py`:

```python
dag = DAG(
    'arxiv_daily_ingestion',
    schedule_interval='0 2 * * *',  # Modify this
    ...
)
```

Common schedules:
- `'0 2 * * *'` - Daily at 2 AM UTC
- `'0 2 * * 0'` - Weekly on Sunday at 2 AM
- `'@daily'` - Once per day
- `'@weekly'` - Once per week
- `None` - Manual trigger only

### Paper Count

Default: 100 papers per run

To change, edit `dags/arxiv_ingestion_dag.py`:

```python
ingest_papers = PythonOperator(
    task_id='ingest_arxiv_papers',
    op_kwargs={
        'max_papers': 100,  # Change this
        'categories': ['cs.AI', 'cs.LG', 'cs.CL'],
    },
)
```

### Categories

Default: `['cs.AI', 'cs.LG', 'cs.CL']`

Available categories:
- `cs.AI` - Artificial Intelligence
- `cs.LG` - Machine Learning
- `cs.CL` - Computation and Language
- `cs.CV` - Computer Vision
- `cs.NE` - Neural and Evolutionary Computing

## Common Tasks

### View DAG Status

```bash
# List all DAGs
docker compose exec airflow-webserver airflow dags list

# Show DAG details
docker compose exec airflow-webserver airflow dags show arxiv_daily_ingestion
```

### Trigger DAG Manually

```bash
# Via CLI
docker compose exec airflow-webserver airflow dags trigger arxiv_daily_ingestion

# Via UI
# Click on DAG → "Trigger DAG" button
```

### Pause/Unpause DAG

```bash
# Pause (stop scheduled runs)
docker compose exec airflow-webserver airflow dags pause arxiv_daily_ingestion

# Unpause (resume scheduled runs)
docker compose exec airflow-webserver airflow dags unpause arxiv_daily_ingestion
```

### View Task Logs

```bash
# View logs for a specific task
docker compose exec airflow-webserver airflow tasks logs \
  arxiv_daily_ingestion ingest_arxiv_papers

# Or view in UI: Click task → "Log" button
```

### Clear Task State

```bash
# Clear failed task to retry
docker compose exec airflow-webserver airflow tasks clear \
  arxiv_daily_ingestion ingest_arxiv_papers

# Clear entire DAG run
docker compose exec airflow-webserver airflow dags clear arxiv_daily_ingestion
```

## Monitoring

### Airflow UI Features

1. **Graph View**: Visual representation of DAG with task status
2. **Tree View**: Timeline of all DAG runs
3. **Gantt Chart**: Task duration visualization
4. **Task Instances**: Detailed view of each task execution
5. **Logs**: Real-time and historical task logs

### Task Status Colors

- **Green**: Success
- **Red**: Failed
- **Orange**: Running
- **Light Blue**: Scheduled
- **Gray**: No status

### Health Checks

```bash
# Check Airflow webserver
curl http://localhost:8080/health

# Check scheduler
docker compose exec airflow-scheduler airflow version

# Check database connection
docker compose exec airflow-postgres pg_isready -U airflow
```

## Troubleshooting

### DAG Not Appearing

```bash
# Check if DAG files are mounted correctly
docker compose exec airflow-webserver ls -la /opt/airflow/dags

# Check for syntax errors
docker compose exec airflow-webserver python /opt/airflow/dags/arxiv_ingestion_dag.py

# View webserver logs
docker compose logs airflow-webserver
```

### Tasks Failing

1. **Check logs**: Click task → "Log" in UI, or use CLI above
2. **Check environment variables**: Ensure `.env` file has all required keys
3. **Check dependencies**: Run `check_dependencies` task first
4. **Check S3/Pinecone connectivity**: Verify AWS credentials and Pinecone API key

### Scheduler Not Running Tasks

```bash
# Check scheduler status
docker compose logs airflow-scheduler

# Restart scheduler
docker compose restart airflow-scheduler

# Check if DAG is unpaused
docker compose exec airflow-webserver airflow dags list | grep arxiv_daily_ingestion
```

### Out of Memory

If tasks fail due to memory:
1. Reduce `max_papers` in DAG configuration
2. Reduce `NUM_WORKERS` in `airflow_helpers.py` (default: 10)
3. Increase EC2 instance size

### Database Issues

```bash
# Reset Airflow database (WARNING: deletes all DAG run history)
docker compose down -v
docker compose up -d airflow-init
docker compose up -d
```

## Advanced Configuration

### Custom Retry Logic

Edit `dags/arxiv_ingestion_dag.py`:

```python
default_args = {
    'retries': 3,  # Number of retries
    'retry_delay': timedelta(minutes=10),  # Wait 10 min between retries
    'retry_exponential_backoff': True,  # Exponential backoff
}
```

### Email Notifications

Add to `default_args`:

```python
default_args = {
    'email': ['admin@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}
```

Requires SMTP configuration in `docker-compose.yml` (the filename stays as-is, but use `docker compose` command).

### Task Timeouts

```python
ingest_papers = PythonOperator(
    task_id='ingest_arxiv_papers',
    execution_timeout=timedelta(hours=2),  # 2 hour timeout
    ...
)
```

## Resource Requirements

- **Minimum**: 4GB RAM, 2 vCPU
- **Recommended**: 8GB RAM, 4 vCPU
- **Airflow overhead**: ~500MB RAM (Postgres + Webserver + Scheduler)

## Security

### Change Default Password

```bash
docker compose exec airflow-webserver airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password your_secure_password

# Then delete default user
docker compose exec airflow-webserver airflow users delete airflow
```

### Restrict Airflow Access

In production, restrict port 8080 to specific IPs in EC2 Security Group.

## Next Steps

- Implement incremental ingestion (only fetch new papers)
- Add more DAGs for different data sources
- Set up alerting (Slack, email)
- Configure Airflow for high availability
- Add data quality checks as separate tasks
