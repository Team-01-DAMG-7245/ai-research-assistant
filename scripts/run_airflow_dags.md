# Running Airflow DAGs

## Option 1: Using Docker (Recommended for Windows)

### Prerequisites
- Docker Desktop installed and running
- Environment variables configured in `.env` file

### Steps

1. **Start Airflow services:**
```bash
cd "C:\Users\Swara\Desktop\Big Data Assignments\final project\ai-research-assistant"
docker-compose -f docker-compose.airflow.yml up -d
```

2. **Wait for services to initialize (30-60 seconds)**

3. **Access Airflow UI:**
   - Open browser: http://localhost:8080
   - Login: `airflow` / `airflow` (default)

4. **Unpause and trigger DAGs:**
   - In Airflow UI, find `arxiv_ingestion` DAG
   - Click toggle to unpause (if paused)
   - Click "Trigger DAG" to run manually
   - Or wait for daily schedule (midnight)

5. **Monitor execution:**
   - Click on DAG name to see task status
   - Click on task to view logs
   - Green = success, Red = failed, Yellow = running

6. **Stop services:**
```bash
docker-compose -f docker-compose.airflow.yml down
```

---

## Option 2: Using WSL2 (Windows Subsystem for Linux)

### Prerequisites
- WSL2 installed
- Ubuntu/Debian distribution

### Steps

1. **Open WSL2 terminal:**
```bash
wsl
```

2. **Navigate to project:**
```bash
cd /mnt/c/Users/Swara/Desktop/Big\ Data\ Assignments/final\ project/ai-research-assistant
```

3. **Install Airflow:**
```bash
pip install apache-airflow==2.7.0
pip install arxiv boto3 openai pinecone-client tiktoken PyMuPDF
```

4. **Set environment variables:**
```bash
export AIRFLOW_HOME=~/airflow
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export OPENAI_API_KEY=your_key
export PINECONE_API_KEY=your_key
export S3_BUCKET_NAME=your_bucket
export PINECONE_INDEX_NAME=your_index
```

5. **Initialize Airflow:**
```bash
airflow db init
airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@example.com --password admin
```

6. **Copy DAGs:**
```bash
mkdir -p $AIRFLOW_HOME/dags
cp -r dags/* $AIRFLOW_HOME/dags/
```

7. **Start scheduler (in one terminal):**
```bash
airflow scheduler
```

8. **Start webserver (in another terminal):**
```bash
airflow webserver --port 8080
```

9. **Access UI:** http://localhost:8080

---

## Option 3: Test Locally (Without Full Airflow)

For quick testing on Windows without Docker/WSL2:

```bash
cd "C:\Users\Swara\Desktop\Big Data Assignments\final project\ai-research-assistant"
python scripts/test_dags.py
```

This runs the DAG tasks directly without Airflow scheduler.

---

## Option 4: Manual Task Execution

Run individual tasks directly:

```python
# In Python shell or script
import sys
import os
sys.path.insert(0, 'dags')

from ingestion_dag import check_new_papers_task

# Mock context
class MockTI:
    def xcom_pull(self, task_ids=None):
        return None

context = {'ti': MockTI()}

# Run task
result = check_new_papers_task(**context)
print(result)
```

---

## Troubleshooting

### Docker Issues
- **Port 8080 already in use**: Change port in docker-compose.airflow.yml
- **Permission errors**: Ensure Docker has proper file permissions
- **Services won't start**: Check Docker Desktop is running

### WSL2 Issues
- **Import errors**: Ensure all dependencies installed
- **Database errors**: Run `airflow db init` again
- **DAGs not appearing**: Check `AIRFLOW_HOME` and DAGs folder path

### Environment Variables
- Ensure `.env` file exists with all required variables
- Check variables are loaded: `echo $AWS_ACCESS_KEY_ID`

---

## Quick Start Commands

### Docker (Easiest for Windows)
```bash
# Start
docker-compose -f docker-compose.airflow.yml up -d

# View logs
docker-compose -f docker-compose.airflow.yml logs -f

# Stop
docker-compose -f docker-compose.airflow.yml down
```

### Local Testing
```bash
python scripts/test_dags.py
```
