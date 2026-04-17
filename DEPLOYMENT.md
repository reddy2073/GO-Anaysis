# Deployment Guide - LegalDebateAI

Production deployment configuration for LegalDebateAI system.

## Overview

This guide covers deploying LegalDebateAI to production environments including cloud platforms, Docker containers, and local servers.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Deployment](#cloud-deployment)
5. [Local Server Deployment](#local-server-deployment)
6. [Performance Optimization](#performance-optimization)
7. [Monitoring & Logging](#monitoring--logging)
8. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Before going live:

- [ ] All 12 tests passing (`python test_scenarios.py`)
- [ ] System validation complete (`python validate_system.py`)
- [ ] API keys configured in `.env` (not in git)
- [ ] Database initialized (`python setup_db.py`)
- [ ] README.md reviewed and updated
- [ ] CHANGELOG.md updated with version
- [ ] Error handling tested
- [ ] Logging configured
- [ ] Performance tested with production data
- [ ] Security review completed
- [ ] Backup strategy defined
- [ ] Rollback plan documented

---

## Environment Configuration

### Local Development
```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-dev-key
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
```

### Staging Environment
```bash
# .env.staging
ANTHROPIC_API_KEY=sk-ant-staging-key
ENVIRONMENT=staging
DEBUG=False
LOG_LEVEL=INFO
CACHE_ENABLED=True
```

### Production Environment
```bash
# .env.production (secure vault)
ANTHROPIC_API_KEY=sk-ant-prod-key
OPENAI_API_KEY=sk-openai-prod-key
GOOGLE_API_KEY=AIza-prod-key
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
CACHE_ENABLED=True
CACHE_TTL=3600
MAX_WORKERS=4
```

### Load from environment
```python
import os
from pathlib import Path

env_file = Path('.env.production')
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set")
```

---

## Docker Deployment

### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run API server
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  legaldebaseai:
    build: .
    container_name: legaldebaseai-api
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - ./db:/app/db
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
    container_name: legaldebaseai-chromadb
    ports:
      - "8001:8000"
    environment:
      - IS_PERSISTENT=True
      - PERSIST_DIRECTORY=/data
    volumes:
      - chromadb_data:/data
    restart: unless-stopped

volumes:
  chromadb_data:
```

### 3. Build and Run

```bash
# Build image
docker build -t legaldebaseai:1.0.0 .

# Run container
docker run -d \
  --name legaldebaseai \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v $(pwd)/db:/app/db \
  legaldebaseai:1.0.0

# Or use docker-compose
docker-compose up -d

# Check status
docker ps
docker logs legaldebaseai

# Stop container
docker stop legaldebaseai
docker remove legaldebaseai
```

---

## Cloud Deployment

### AWS Lambda

```python
# lambda_handler.py
from debate_engine import run_debate
import json

def lambda_handler(event, context):
    try:
        go_text = event.get('go_text')
        use_cache = event.get('use_cache', True)
        
        result = run_debate(go_text, use_cache=use_cache)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

**Deploy:**
```bash
pip install -r requirements.txt -t ./package
cd package
zip -r ../deployment.zip .
cd ..
zip deployment.zip lambda_handler.py

aws lambda create-function \
  --function-name legaldebaseai \
  --runtime python3.11 \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://deployment.zip
```

### Google Cloud Run

```bash
# Create Dockerfile (see above)
# Set up gcloud
gcloud auth login
gcloud config set project your-project

# Build and deploy
gcloud run deploy legaldebaseai \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars ANTHROPIC_API_KEY=sk-ant-...
```

### Azure App Service

```bash
# Create app service plan
az appservice plan create \
  --name legaldebaseai-plan \
  --resource-group mygroup \
  --sku B1 --is-linux

# Deploy
az webapp create \
  --resource-group mygroup \
  --plan legaldebaseai-plan \
  --name legaldebaseai

# Configure environment
az webapp config appsettings set \
  --resource-group mygroup \
  --name legaldebaseai \
  --settings ANTHROPIC_API_KEY=sk-ant-...
```

---

## Local Server Deployment

### Using Gunicorn

```bash
# Install
pip install gunicorn

# Run
gunicorn -w 4 -b 0.0.0.0:8000 api:app

# With systemd (Linux)
sudo cp legaldebaseai.service /etc/systemd/system/
sudo systemctl start legaldebaseai
sudo systemctl status legaldebaseai
```

### Systemd Service File

Create `/etc/systemd/system/legaldebaseai.service`:

```ini
[Unit]
Description=LegalDebateAI Service
After=network.target

[Service]
Type=notify
User=appuser
WorkingDirectory=/opt/legaldebaseai
Environment="PATH=/opt/legaldebaseai/venv/bin"
EnvironmentFile=/etc/legaldebaseai/.env.production
ExecStart=/opt/legaldebaseai/venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable legaldebaseai
sudo systemctl start legaldebaseai
```

### Using Supervisor

```ini
[program:legaldebaseai]
command=/opt/legaldebaseai/venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000
directory=/opt/legaldebaseai
user=appuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/legaldebaseai.log
```

---

## Performance Optimization

### Database
```python
# Enable connection pooling
from chromadb import PersistentClient

client = PersistentClient(
    path="./db/chromadb",
    settings=Settings(
        max_connections=10,
        connection_timeout=30
    )
)
```

### Caching Strategy
```python
# Enable aggressive caching
from config import CACHE_ENABLED, CACHE_TTL

CACHE_ENABLED = True
CACHE_TTL = 3600  # 1 hour

# Clear stale cache
from agents.cache_manager import clear_cache
# Scheduled job: clear_cache() daily
```

### Model Selection
```python
# Use Haiku for speed in production
QUALITY_CLOUD_MODEL = "claude-haiku-3-5"  # Fast
# Or mix: Haiku for debates, Sonnet for analysis
```

### Resource Allocation
```python
import multiprocessing
MAX_WORKERS = min(4, multiprocessing.cpu_count())
BATCH_SIZE = 10
MAX_CHUNKS = 100
```

---

## Monitoring & Logging

### Setup Logging

```python
# logging_config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Metrics to Track
- API response time (target: < 5 min for full analysis)
- Cache hit rate (target: > 50%)
- Error rate (target: < 0.1%)
- Token usage (cost tracking)
- Database query time
- Memory usage

### Health Check Endpoint

```python
# In api.py
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/metrics")
async def metrics():
    return {
        "cache_size": get_cache_size(),
        "database_collections": get_collections_count(),
        "uptime_seconds": get_uptime()
    }
```

---

## Troubleshooting

### High Memory Usage
```python
# Reduce chunk size
MAX_CHUNKS = 50  # Was 100

# Reduce worker count
MAX_WORKERS = 2  # Was 4

# Enable garbage collection
import gc
gc.collect()
```

### Slow Analysis
```python
# Enable caching
use_cache=True

# Use Haiku model
QUALITY_CLOUD_MODEL = "claude-haiku-3-5"

# Monitor database
# Check ChromaDB is responding
```

### Database Issues
```bash
# Reinitialize database
python setup_db.py

# Check database size
du -sh ./db/chromadb

# Cleanup old cache
rm -rf db/cache/
```

### API Errors
```bash
# Check logs
tail -f logs/app.log

# Verify configuration
python validate_system.py

# Check API key
echo $ANTHROPIC_API_KEY
```

---

## Rollback Procedure

### If deployment fails:

```bash
# Keep previous version
cp -r app app.backup.1.0.0

# Revert to last working
git checkout v0.9.0
pip install -r requirements.txt

# Restart service
docker restart legaldebaseai
# or
systemctl restart legaldebaseai
```

---

## Backup Strategy

### Daily Backup
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/legaldebaseai"
mkdir -p $BACKUP_DIR

# Backup database
cp -r db/chromadb $BACKUP_DIR/chromadb.$(date +%Y%m%d)

# Backup cache
cp -r db/cache $BACKUP_DIR/cache.$(date +%Y%m%d)

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -mtime +7 -delete
```

### Restore from Backup
```bash
cp -r /backups/legaldebaseai/chromadb.20260417 db/chromadb
systemctl restart legaldebaseai
```

---

## Security Checklist

- [ ] API keys in environment variables (not in code)
- [ ] HTTPS enabled (TLS 1.2+)
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints
- [ ] CORS properly configured
- [ ] Secrets encrypted at rest
- [ ] Regular dependency updates
- [ ] Security scanning enabled (bandit)
- [ ] Firewall configured
- [ ] Access logs enabled
- [ ] IP whitelisting (if applicable)
- [ ] DDoS protection configured

---

## Scaling Strategy

### Horizontal Scaling
```yaml
# docker-compose with load balancer
version: '3.8'
services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      
  api1:
    build: .
    environment:
      - INSTANCE=1
      
  api2:
    build: .
    environment:
      - INSTANCE=2
      
  api3:
    build: .
    environment:
      - INSTANCE=3
```

### Vertical Scaling
- Upgrade machine CPU/RAM
- Increase worker processes
- Increase cache size
- Use faster models locally (Ollama)

---

## Maintenance

### Weekly
- Check logs for errors
- Monitor resource usage
- Verify backups

### Monthly
- Update dependencies: `pip install -r requirements.txt --upgrade`
- Run security scan: `bandit -r .`
- Performance analysis
- Cache cleanup

### Quarterly
- Major dependency updates
- Performance optimization
- Security audit
- Disaster recovery drill

---

## Support & Contact

- **Issues**: GitHub Issues
- **Documentation**: README.md
- **Monitoring**: Set up Sentry/DataDog
- **Alerts**: Configure email/Slack notifications

---

**Last Updated**: April 17, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
