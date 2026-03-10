# Setup Guide - Agent Orchestration Platform

## Project Size

### Disk Space:
- **Total project size:** ~3.7 MB
- **Backend code:** ~2.8 MB
- **Very lightweight** - minimal dependencies

### Code Statistics:
- **Python files:** 176 files
- **Total lines of code:** 46,431 lines
- **Database tables:** 40+ tables
- **API endpoints:** 100+ endpoints

**This is a lean, well-organized codebase - not bloated.**

---

## Prerequisites

### 1. PostgreSQL Database

**Install PostgreSQL:**

**macOS (using Homebrew):**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download from: https://www.postgresql.org/download/windows/

### 2. Python Environment

**Requirements:**
- Python 3.11+ (recommended)
- pip (Python package manager)

**Check your Python version:**
```bash
python --version  # Should be 3.11 or higher
```

---

## Setup Steps

### Step 1: Install Python Dependencies

```bash
# Navigate to project directory
cd /path/to/agent-orchestration

# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# OR install core dependencies manually:
pip install fastapi sqlalchemy asyncpg alembic pydantic python-dotenv
```

### Step 2: Create PostgreSQL Database

```bash
# Option A: Using createdb command (if PostgreSQL is in PATH)
createdb agent_orchestration

# Option B: Using psql
psql -U postgres -c "CREATE DATABASE agent_orchestration;"

# Option C: Using PostgreSQL GUI (pgAdmin, DBeaver, etc.)
# Just create a database named "agent_orchestration"
```

**Verify database was created:**
```bash
psql -U postgres -l | grep agent_orchestration
```

### Step 3: Run Database Migrations

```bash
# Navigate to project root
cd /path/to/agent-orchestration

# Run Alembic migrations to create all tables
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20251218_2000, add workflow templates
INFO  [alembic.runtime.migration] Running upgrade 20251218_2000 -> 20251218_2100, add multi llm routing
INFO  [alembic.runtime.migration] Running upgrade 20251218_2100 -> 20251219_0100, add hitl workflows
INFO  [alembic.runtime.migration] Running upgrade 20251219_0100 -> 20251219_0200, add ab testing
INFO  [alembic.runtime.migration] Running upgrade 20251219_0200 -> 20251219_0300, add realtime
INFO  [alembic.runtime.migration] Running upgrade 20251219_0300 -> 20251219_0400, add analytics
INFO  [alembic.runtime.migration] Running upgrade 20251219_0400 -> 20251219_0500, add marketplace
INFO  [alembic.runtime.migration] Running upgrade 20251219_0500 -> 20251219_0600, add whitelabel
INFO  [alembic.runtime.migration] Running upgrade 20251219_0600 -> 20251219_0700, add security
INFO  [alembic.runtime.migration] Running upgrade 20251219_0700 -> 20251219_0800, add multicloud
INFO  [alembic.runtime.migration] Running upgrade 20251219_0800 -> 20251219_0900, add ml routing
```

This creates all 40+ database tables.

### Step 4: Verify Setup

```bash
# Check database tables were created
psql -U postgres -d agent_orchestration -c "\dt"

# Should show 40+ tables:
# - agents, workflows, executions
# - integrations, llm_models
# - dashboards, metrics
# - marketplace_agents, partners
# - audit_logs, roles
# - deployments, cloud_accounts
# etc.
```

---

## Database Size

### Empty Database (after migrations):
- **Initial size:** ~5-10 MB (schema only)
- **With sample data from demos:** ~50-100 MB
- **Production (1 year):** ~1-5 GB (depends on volume)

**The database is lightweight and scales efficiently.**

---

## Running Demos

Once setup is complete, run any demo:

```bash
# Integration Marketplace demo
python backend/demo_integration_marketplace.py

# Analytics dashboard demo
python backend/demo_analytics.py

# Security & compliance demo
python backend/demo_security.py

# See all demos
ls backend/demo_*.py
```

---

## Connection String

The default connection string is:
```
postgresql+asyncpg://localhost/agent_orchestration
```

If you need to customize (different user, password, host):

**Create a `.env` file:**
```bash
DATABASE_URL=postgresql+asyncpg://username:password@host:port/agent_orchestration
```

**Or update in each demo file:**
```python
DATABASE_URL = "postgresql+asyncpg://your_user:your_pass@localhost/agent_orchestration"
```

---

## Troubleshooting

### Issue: PostgreSQL not installed

**Solution:**
```bash
# macOS
brew install postgresql@14

# Ubuntu/Debian
sudo apt install postgresql

# Windows
# Download from postgresql.org
```

### Issue: Database connection refused

**Solution:**
```bash
# Check if PostgreSQL is running
# macOS
brew services list | grep postgresql

# Ubuntu
sudo systemctl status postgresql

# Start PostgreSQL if stopped
# macOS
brew services start postgresql@14

# Ubuntu
sudo systemctl start postgresql
```

### Issue: Permission denied creating database

**Solution:**
```bash
# Create database as postgres user
sudo -u postgres createdb agent_orchestration

# OR grant permissions to your user
sudo -u postgres psql
# In psql:
CREATE ROLE your_username WITH LOGIN PASSWORD 'your_password';
ALTER ROLE your_username CREATEDB;
```

### Issue: Alembic migrations fail

**Solution:**
```bash
# Check alembic.ini configuration
cat alembic.ini | grep sqlalchemy.url

# Make sure it points to correct database
# Update if needed:
sqlalchemy.url = postgresql+asyncpg://localhost/agent_orchestration

# Then retry:
alembic upgrade head
```

### Issue: Import errors when running demos

**Solution:**
```bash
# Make sure you're in project root
cd /path/to/agent-orchestration

# Install dependencies
pip install fastapi sqlalchemy asyncpg alembic pydantic

# Run from project root
python backend/demo_*.py
```

---

## Quick Setup Summary

**Complete setup in 4 commands:**

```bash
# 1. Create database
createdb agent_orchestration

# 2. Run migrations
alembic upgrade head

# 3. Install dependencies (if needed)
pip install fastapi sqlalchemy asyncpg alembic pydantic

# 4. Run a demo
python backend/demo_analytics.py
```

**Total time: 2-5 minutes**

---

## System Requirements

### Minimum:
- **OS:** macOS, Linux, or Windows
- **RAM:** 2 GB
- **Disk:** 100 MB for code + 1 GB for database
- **Python:** 3.11+
- **PostgreSQL:** 12+

### Recommended:
- **OS:** macOS or Linux
- **RAM:** 4 GB+
- **Disk:** 500 MB for code + 5 GB for database
- **Python:** 3.11+
- **PostgreSQL:** 14+

---

## Next Steps

After setup:
1. ✅ Run a demo: `python backend/demo_integration_marketplace.py`
2. ✅ Read **HOW_IT_WORKS.md** for architecture
3. ✅ Read **DEMO_GUIDE.md** for all available demos
4. ✅ Explore the code in `backend/shared/` and `backend/api/`

---

**Need help?** Check the troubleshooting section above or open a GitHub issue.
