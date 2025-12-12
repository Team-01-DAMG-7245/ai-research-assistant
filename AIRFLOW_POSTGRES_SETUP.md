# Airflow PostgreSQL Setup Guide

This guide explains how to configure Airflow to use PostgreSQL instead of SQLite.

## Why PostgreSQL?

- **Better Performance**: PostgreSQL handles concurrent operations much better than SQLite
- **Production Ready**: SQLite is not recommended for production environments
- **Scalability**: PostgreSQL supports multiple concurrent connections and better task execution
- **Executor Support**: Required for `LocalExecutor` and `CeleryExecutor` (SQLite only works with `SequentialExecutor`)

## Setup Options

### Option 1: Using Docker Compose (Recommended)

PostgreSQL has been added to `docker-compose.yml`. Follow these steps:

#### 1. Start PostgreSQL

```bash
# Start PostgreSQL service
docker compose up -d postgres

# Verify it's running
docker compose ps postgres
```

#### 2. Configure Airflow Connection String

Update your `airflow.cfg` or set environment variable:

**In airflow.cfg:**
```ini
[database]
sql_alchemy_conn = postgresql+psycopg2://airflow:airflow@localhost:5432/airflow
```

**Or set environment variable:**
```bash
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
```

**Connection string format:**
```
postgresql+psycopg2://<username>:<password>@<host>:<port>/<database>
```

#### 3. Initialize Airflow Database

```bash
source venv/bin/activate
export AIRFLOW_HOME=/Users/natnichalerd/ai-research-assistant/airflow_home

# Initialize the database (creates tables)
airflow db migrate

# Create an admin user (if you haven't already)
airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin
```

#### 4. Verify Connection

```bash
# Test database connection
airflow db check
```

### Option 2: Local PostgreSQL Installation

If you prefer to install PostgreSQL locally:

#### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

#### 2. Create Airflow Database and User

```bash
# Connect to PostgreSQL
psql postgres

# Create database and user
CREATE DATABASE airflow;
CREATE USER airflow WITH PASSWORD 'airflow';
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
\q
```

#### 3. Configure Airflow

Update `airflow.cfg`:
```ini
[database]
sql_alchemy_conn = postgresql+psycopg2://airflow:airflow@localhost:5432/airflow
```

Or set environment variable:
```bash
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
```

#### 4. Initialize Airflow Database

```bash
source venv/bin/activate
export AIRFLOW_HOME=/Users/natnichalerd/ai-research-assistant/airflow_home
airflow db migrate
```

## Migration from SQLite to PostgreSQL

If you have existing data in SQLite that you want to migrate:

### Method 1: Fresh Start (Recommended for Development)

1. Backup your DAGs (they're in `dags/` folder)
2. Delete the SQLite database: `rm airflow_home/airflow.db`
3. Initialize PostgreSQL: `airflow db migrate`
4. Recreate users: `airflow users create ...`

### Method 2: Export/Import (For Production)

1. **Export from SQLite:**
```bash
# Export DAGs, Variables, Connections, etc.
airflow db export-connections connections.json
airflow variables export variables.json
```

2. **Initialize PostgreSQL:**
```bash
airflow db migrate
```

3. **Import to PostgreSQL:**
```bash
airflow db import-connections connections.json
airflow variables import variables.json
```

**Note:** Task history and DAG runs cannot be easily migrated. Consider if you need historical data.

## Updating Executor (Optional but Recommended)

With PostgreSQL, you can use `LocalExecutor` for better performance:

**In airflow.cfg:**
```ini
[core]
executor = LocalExecutor
```

**Benefits:**
- Can run multiple tasks in parallel
- Better resource utilization
- Still runs on a single machine (no Celery setup needed)

## Environment Variables (Alternative Configuration)

Instead of editing `airflow.cfg`, you can use environment variables:

```bash
export AIRFLOW_HOME=/Users/natnichalerd/ai-research-assistant/airflow_home
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
export AIRFLOW__CORE__EXECUTOR="LocalExecutor"
```

## Verify Setup

```bash
# Check database connection
airflow db check

# List DAGs
airflow dags list

# Start webserver (test)
airflow webserver --port 8080
```

## Troubleshooting

### Connection Refused

- **Docker**: Make sure PostgreSQL container is running: `docker compose ps postgres`
- **Local**: Check PostgreSQL service: `brew services list` or `sudo systemctl status postgresql`

### Authentication Failed

- Verify username/password in connection string
- Check PostgreSQL user permissions: `psql -U postgres -c "\du"`

### Database Does Not Exist

- Create the database: `createdb -U airflow airflow`
- Or connect to PostgreSQL and run: `CREATE DATABASE airflow;`

### psycopg2 Module Not Found

- Install: `pip install psycopg2-binary`
- Already in `requirements.txt`, so run: `pip install -r requirements.txt`

## Security Notes

⚠️ **For Production:**
- Use strong passwords (not "airflow")
- Store credentials in environment variables or secrets manager
- Use SSL connections: `postgresql+psycopg2://user:pass@host:5432/db?sslmode=require`
- Restrict database access with firewall rules
- Use separate database users with minimal required permissions

## Quick Start Commands

```bash
# 1. Start PostgreSQL (Docker)
docker compose up -d postgres

# 2. Set environment
source venv/bin/activate
export AIRFLOW_HOME=/Users/natnichalerd/ai-research-assistant/airflow_home
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"

# 3. Initialize database
airflow db migrate

# 4. Create admin user
airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin

# 5. Verify
airflow db check
```

## Next Steps

After setting up PostgreSQL:
1. ✅ Your DAGs will work better with concurrent execution
2. ✅ Consider switching to `LocalExecutor` for parallel task execution
3. ✅ Set up proper backup strategy for PostgreSQL database
4. ✅ Configure connection pooling settings in `airflow.cfg` if needed
 

