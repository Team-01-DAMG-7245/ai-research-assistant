# Airflow DAGs for Research Paper Processing Pipeline

This directory contains Apache Airflow DAGs for orchestrating the research paper ingestion, processing, and embedding pipeline.

## Directory Structure

```
dags/
├── ingestion_dag.py          # arXiv paper ingestion DAG
├── processing_dag.py          # PDF processing and chunking DAG
├── embedding_dag.py           # Embedding generation and Pinecone upsert DAG
├── common/                    # Shared utility modules
│   ├── __init__.py
│   ├── arxiv_utils.py         # arXiv API utilities
│   ├── s3_utils.py            # S3 operations utilities
│   ├── processing_utils.py    # PDF extraction and chunking utilities
│   └── embedding_utils.py    # OpenAI embedding utilities
└── README.md                  # This file
```

## DAGs Overview

### 1. arxiv_ingestion (Daily Schedule)

**Schedule**: `@daily` (runs at midnight)

**Purpose**: Collects new research papers from arXiv API

**Tasks**:
- `check_new_papers_task`: Queries arXiv for papers published in last 24 hours
- `download_pdfs_task`: Downloads PDFs from arXiv with rate limiting
- `upload_to_s3_bronze_task`: Uploads PDFs to S3 bronze layer and stores metadata

**Dependencies**: `check_new_papers >> download_pdfs >> upload_to_s3_bronze`

---

### 2. document_processing (Triggered)

**Schedule**: `None` (triggered by ingestion_dag completion)

**Purpose**: Processes raw PDFs into text chunks

**Tasks**:
- `list_unprocessed_papers_task`: Lists papers with status='raw' from SQLite
- `extract_text_parallel_task`: Extracts text from PDFs using 10 parallel workers
- `chunk_text_task`: Chunks text into 512-token segments with 50-token overlap
- `upload_chunks_to_s3_silver_task`: Uploads chunks to S3 silver layer

**Dependencies**: `wait_for_ingestion >> list_unprocessed >> extract_text_parallel >> chunk_text >> upload_chunks_to_s3_silver`

**Trigger**: Uses `ExternalTaskSensor` to wait for `arxiv_ingestion` DAG completion

---

### 3. generate_embeddings (Triggered)

**Schedule**: `None` (triggered by processing_dag completion)

**Purpose**: Generates embeddings and upserts to Pinecone

**Tasks**:
- `list_new_chunks_task`: Lists chunks from S3 that don't have embeddings yet
- `generate_embeddings_batch_task`: Generates embeddings using OpenAI API in batches
- `upsert_to_pinecone_task`: Upserts embeddings to Pinecone vector database

**Dependencies**: `wait_for_processing >> list_new_chunks >> generate_embeddings_batch >> upsert_to_pinecone`

**Trigger**: Uses `ExternalTaskSensor` to wait for `document_processing` DAG completion

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install apache-airflow==2.7.0
pip install arxiv boto3 openai pinecone-client tiktoken PyMuPDF
```

### 2. Configure Environment Variables

Set the following environment variables in your Airflow environment:

```bash
# AWS Configuration
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=research-data

# OpenAI Configuration
export OPENAI_API_KEY=your_openai_key

# Pinecone Configuration
export PINECONE_API_KEY=your_pinecone_key
export PINECONE_INDEX_NAME=research-papers

# Database Configuration
export TASK_DB_PATH=data/tasks.db

# Airflow Configuration (optional)
export AIRFLOW_EMAIL=admin@example.com
export PROCESSING_WORKERS=10
export CHUNK_SIZE=512
export CHUNK_OVERLAP=50
```

### 3. Initialize Airflow Database

```bash
airflow db init
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

### 4. Set Airflow Home Directory

```bash
export AIRFLOW_HOME=/path/to/your/airflow/home
```

### 5. Copy DAGs to Airflow DAGs Folder

```bash
# If AIRFLOW_HOME is set
cp -r dags/ $AIRFLOW_HOME/dags/

# Or symlink
ln -s /path/to/project/dags $AIRFLOW_HOME/dags
```

### 6. Start Airflow Services

```bash
# Start scheduler
airflow scheduler

# Start webserver (in another terminal)
airflow webserver --port 8080
```

### 7. Access Airflow UI

Open browser to `http://localhost:8080` and login with your credentials.

---

## DAG Execution Flow

```
Day 1 (Midnight):
┌─────────────────────┐
│ arxiv_ingestion     │
│ (Daily Schedule)    │
└──────────┬──────────┘
           │
           ▼
    [New Papers Downloaded]
           │
           ▼
┌─────────────────────┐
│ document_processing │
│ (Triggered)         │
└──────────┬──────────┘
           │
           ▼
    [PDFs Processed]
           │
           ▼
┌─────────────────────┐
│ generate_embeddings │
│ (Triggered)         │
└─────────────────────┘
```

---

## Monitoring and Troubleshooting

### View DAG Status

```bash
# List all DAGs
airflow dags list

# Show DAG details
airflow dags show arxiv_ingestion

# Show task details
airflow tasks list arxiv_ingestion
```

### Check Logs

```bash
# View task logs
airflow tasks logs arxiv_ingestion check_new_papers_task 2024-01-01
```

### Manual Trigger

```bash
# Trigger DAG manually
airflow dags trigger arxiv_ingestion

# Trigger specific task
airflow tasks run arxiv_ingestion check_new_papers_task 2024-01-01
```

### Common Issues

1. **DAG not appearing**: Check `AIRFLOW_HOME` and ensure DAGs folder is correct
2. **Import errors**: Ensure all dependencies are installed and `common/` module is accessible
3. **XCom errors**: Check that tasks are properly connected and returning data
4. **S3/AWS errors**: Verify AWS credentials and bucket permissions
5. **Pinecone errors**: Check API key and index name configuration

---

## Testing DAGs Locally

### Test Individual Tasks

```python
from dags.ingestion_dag import check_new_papers_task
from airflow.utils.context import Context

# Create mock context
context = {}

# Run task
result = check_new_papers_task(**context)
print(result)
```

### Test DAG Structure

```bash
# Validate DAG syntax
python dags/ingestion_dag.py

# List DAG imports
airflow dags list-import-errors
```

---

## Production Deployment

### Using Docker

See `docker-compose.yml` for Airflow service configuration.

### Using Kubernetes

Deploy Airflow using the official Helm chart or custom Kubernetes manifests.

### Environment Variables

Ensure all environment variables are set in your production environment (use secrets management).

---

## Performance Tuning

- **Parallel Processing**: Adjust `PROCESSING_WORKERS` based on available CPU cores
- **Batch Sizes**: Tune embedding batch sizes based on API rate limits
- **Retry Logic**: Adjust retry counts and delays based on failure patterns
- **Timeouts**: Set appropriate `execution_timeout` values for long-running tasks

---

## Email Notifications

Configure email settings in `airflow.cfg`:

```ini
[smtp]
smtp_host = smtp.gmail.com
smtp_starttls = True
smtp_ssl = False
smtp_user = your_email@gmail.com
smtp_password = your_password
smtp_port = 587
smtp_mail_from = airflow@example.com
```

---

## Security Considerations

1. **Credentials**: Never commit API keys or credentials to version control
2. **IAM Roles**: Use IAM roles instead of access keys when possible
3. **Network Security**: Restrict Airflow webserver access to internal networks
4. **Database Security**: Use strong passwords for Airflow metadata database
5. **Secrets Management**: Use Airflow Connections or external secrets backends

---

## Support

For issues or questions:
- Check Airflow logs: `$AIRFLOW_HOME/logs/`
- Review DAG code for syntax errors
- Verify environment variables are set correctly
- Check external service connectivity (arXiv, S3, OpenAI, Pinecone)
