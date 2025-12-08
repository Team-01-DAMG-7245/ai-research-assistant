# Troubleshooting Guide

## Issue: Tasks Failing with "LangGraph is required" Error

### Problem
Tasks are failing immediately with the error:
```
LangGraph is required. Install it with: pip install langgraph
```

### Root Cause
The `langgraph` package is missing from the Python environment where the FastAPI server is running.

### Solution

1. **If using a virtual environment:**
   ```bash
   cd ai-research-assistant
   source venv/bin/activate  # or: source source/bin/activate
   pip install langgraph
   ```

2. **If using system Python:**
   ```bash
   cd ai-research-assistant
   pip install langgraph
   # or
   pip3 install langgraph
   ```

3. **Install all requirements:**
   ```bash
   cd ai-research-assistant
   pip install -r requirements.txt
   ```

4. **Restart the FastAPI server:**
   ```bash
   # Stop the current server (Ctrl+C)
   # Then restart:
   uvicorn src.api.main:app --reload
   ```

### Verification

Run the configuration checker:
```bash
python3 scripts/check_config.py
```

All services should show ✅ green checkmarks.

### Check Failed Tasks

To see detailed error messages for failed tasks:
```bash
python3 scripts/check_failed_tasks.py
```

## Other Common Issues

### 1. Missing Environment Variables

**Symptoms:** Tasks fail with API key errors

**Solution:**
1. Create a `.env` file in `ai-research-assistant/` directory
2. Add required variables:
   ```bash
   OPENAI_API_KEY=sk-...
   PINECONE_API_KEY=...
   PINECONE_INDEX_NAME=your-index-name
   S3_BUCKET_NAME=your-bucket-name
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```
3. Restart FastAPI server

### 2. Pinecone Index Empty

**Symptoms:** Tasks complete but with no results

**Solution:**
1. Run data ingestion scripts:
   ```bash
   python3 scripts/ingest_arxiv_papers.py
   python3 scripts/embed_chunks_to_pinecone.py
   ```

### 3. API Rate Limits

**Symptoms:** Tasks fail with rate limit errors

**Solution:**
1. Check OpenAI API usage dashboard
2. Wait for rate limit window to reset
3. Consider upgrading API tier

## Diagnostic Tools

### Configuration Checker
```bash
python3 scripts/check_config.py
```
Checks all environment variables and tests service connectivity.

### Failed Tasks Analyzer
```bash
python3 scripts/check_failed_tasks.py
```
Shows detailed error messages for all failed tasks.

### Check Logs
- FastAPI server logs: Check terminal where `uvicorn` is running
- Agent logs: `src/logs/search_agent.log`, `synthesis_agent.log`, etc.
- Workflow logs: `src/logs/workflow.log`

## Quick Fix Checklist

- [ ] Install missing dependencies: `pip install -r requirements.txt`
- [ ] Verify `.env` file exists and has all required variables
- [ ] Run `python3 scripts/check_config.py` - all should be ✅
- [ ] Restart FastAPI server after making changes
- [ ] Check FastAPI server logs for detailed errors
- [ ] Verify Pinecone index has data
- [ ] Check internet connectivity

