# PostgreSQL Setup Guide

This guide documents how to set up and run the Agent Orchestration Platform with PostgreSQL.

## Why PostgreSQL over SQLite?

| Aspect | SQLite | PostgreSQL |
|--------|--------|------------|
| **Data Persistence** | Relative path file - easily lost | Proper database server |
| **Concurrency** | Single writer | Multiple concurrent connections |
| **Scalability** | Single machine | Horizontal scaling possible |
| **Production Ready** | No | Yes |

**Use PostgreSQL for anything beyond quick local testing.**

---

## Prerequisites

### macOS (Homebrew)

```bash
# Install PostgreSQL (if not installed)
brew install postgresql@14

# Start PostgreSQL
brew services start postgresql@14

# Verify it's running
pg_isready
# Expected output: /tmp:5432 - accepting connections
```

### Linux (Ubuntu/Debian)

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL
sudo service postgresql start

# Verify it's running
pg_isready
```

---

## Database Setup

### Option 1: Use Your System User (Simplest for Local Dev)

On macOS, PostgreSQL typically allows your system user to connect without a password:

```bash
# Create the database (uses your system username)
createdb agent_orchestration

# Verify it works
psql agent_orchestration -c "SELECT 'Connected!' as status;"
```

### Option 2: Create a Dedicated User

```bash
# Create user and database
psql postgres -c "CREATE USER agent_user WITH PASSWORD 'agent_password' CREATEDB;"
psql postgres -c "CREATE DATABASE agent_orchestration OWNER agent_user;"

# Verify connection
PGPASSWORD=agent_password psql -h localhost -U agent_user -d agent_orchestration -c "SELECT 'Connected!';"
```

---

## Environment Configuration

Edit `.env` in the `agent-orchestration` directory:

```bash
# ============================================================================
# Database (PostgreSQL)
# ============================================================================
USE_SQLITE=false
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agent_orchestration

# Option 1: Using system user (macOS default)
POSTGRES_USER=your_mac_username
POSTGRES_PASSWORD=

# Option 2: Using dedicated user
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=agent_password
```

### Important Notes

1. **Database name matters**: Use `agent_orchestration` (not `agent_orchestrator`)
2. **Empty password**: On macOS with system user, leave `POSTGRES_PASSWORD=` empty
3. **USE_SQLITE=false**: Must be set to use PostgreSQL

---

## Running Migrations

Before starting the server for the first time (or after pulling new code):

```bash
cd agent-orchestration/backend
export PYTHONPATH="$(dirname $(pwd)):$PYTHONPATH"
export USE_SQLITE=false
python -m alembic upgrade head
```

---

## Starting the Server

**Always use `run_api_postgres.sh` for PostgreSQL:**

```bash
cd agent-orchestration
./run_api_postgres.sh
```

You should see:
```
Starting Agent Orchestration Platform API...
  Directory: /path/to/agent-orchestration
  Database: PostgreSQL (username@localhost:5432/agent_orchestration)

Running API V1 (main.py)...
```

### Verify Correct Database

Check the startup output shows:
- `agent_orchestration` (correct) - NOT `agent_orchestrator`
- Your username or `agent_user`

---

## Troubleshooting

### Issue: "Connection refused"

PostgreSQL isn't running.

```bash
# macOS
brew services start postgresql@14

# Linux
sudo service postgresql start
```

### Issue: "role does not exist"

The PostgreSQL user doesn't exist.

```bash
# Check existing users
psql postgres -c "SELECT rolname FROM pg_roles;"

# Create user if needed
psql postgres -c "CREATE USER your_username WITH CREATEDB;"
```

### Issue: "database does not exist"

```bash
createdb agent_orchestration
```

### Issue: JSON parsing error with CORS_ORIGINS

The `run_api_postgres.sh` script was trying to export complex JSON values. This is fixed - the script now only loads simple `POSTGRES_*` variables.

### Issue: Integration data lost after restart

**Causes:**
1. Wrong database name (`agent_orchestrator` vs `agent_orchestration`)
2. Using SQLite mode instead of PostgreSQL
3. Script loading wrong `.env` file

**Verify:**
```bash
# Check which database has your data
psql agent_orchestration -c "SELECT COUNT(*) FROM integration_installations;"
```

### Issue: Server shows wrong database name

Check your `.env` file:
```bash
grep POSTGRES_DB .env
# Should show: POSTGRES_DB=agent_orchestration
```

---

## Quick Reference Commands

```bash
# Check PostgreSQL status
pg_isready

# Connect to database
psql agent_orchestration

# List all tables
psql agent_orchestration -c "\dt"

# Check integration tables
psql agent_orchestration -c "SELECT name, slug FROM integrations;"

# Check installed integrations
psql agent_orchestration -c "SELECT i.name, ii.status FROM integration_installations ii JOIN integrations i ON ii.integration_id = i.integration_id;"

# Run migrations
cd backend && python -m alembic upgrade head

# Start server
./run_api_postgres.sh
```

---

## File Reference

| File | Purpose |
|------|---------|
| `.env` | Database credentials and settings |
| `run_api_postgres.sh` | Start server with PostgreSQL |
| `run_api.sh` | Start server (defaults to SQLite) |
| `backend/alembic/` | Database migrations |
| `backend/shared/config.py` | Settings loader |

---

## Summary Checklist

Before running the server:

- [ ] PostgreSQL is running (`pg_isready`)
- [ ] Database exists (`agent_orchestration`)
- [ ] `.env` has `USE_SQLITE=false`
- [ ] `.env` has `POSTGRES_DB=agent_orchestration`
- [ ] `.env` has correct `POSTGRES_USER`
- [ ] Migrations are up to date (`alembic upgrade head`)
- [ ] Using `./run_api_postgres.sh` (not `run_api.sh`)
