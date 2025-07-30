# Sync Service

Real-time data synchronization from SQL Server to PostgreSQL using Redis.

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://ghcr.io/bl4ck0z/sync-service)
[![Version](https://img.shields.io/badge/version-1.3-blue.svg)](https://github.com/bl4ck0z/sync-service)

## Quick Start

```bash
git clone https://github.com/Bl4ck0z/sync-service.git
cd sync-service
cp .env.example .env
nano .env                    # Configure your databases
docker volume create sync_logs
docker compose up -d
```

## Configuration

Edit `.env` with your database details:

```bash
# SQL Server (Source)
MSSQL_HOST=your_sql_server
MSSQL_DATABASE=your_database  
MSSQL_USER=readonly_user
MSSQL_PASSWORD=your_password
MSSQL_VIEW=your_view_name

# PostgreSQL (Target)  
PG_HOST=postgres
PG_DATABASE=target_database
PG_USER=postgres_user
PG_PASSWORD=your_password
PG_TABLE_VISTA=target_table

# Redis (Message Queue)
REDIS_HOST=redis
REDIS_PASSWORD=your_redis_password
```

## Prerequisites

Running services:
- PostgreSQL database (target)
- Redis server (message queue)  
- SQL Server access (source)

## Monitoring

```bash
# View logs
docker compose logs -f

# Check status
docker compose ps

# Stats appear every 5 minutes:
# [STATS] Uptime: 2h15m | Processed: 1,247 | Queue: 0 | Rate: 12.3/sec | Errors: 0
```

## Management

```bash
# Start
docker compose up -d

# Stop  
docker compose down

# Restart
docker compose restart

# Update to latest
docker compose pull
docker compose up -d
```

## Database Setup

**PostgreSQL target table:**
```sql
CREATE TABLE your_target_table (
    primary_key VARCHAR(50) PRIMARY KEY,
    field1 VARCHAR(100),
    field2 DATE,
    last_modified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**SQL Server source view must include:**
- Primary key column
- `ULTIMA_MODIFICACION` column (DATETIME)
- Data columns to sync

## Troubleshooting

**Service won't start:**
```bash
docker compose logs sync-service
# Check database credentials in .env
```

**No data syncing:**
```bash
# Verify source view has ULTIMA_MODIFICACION column
# Confirm PostgreSQL table exists
# Check network connectivity
```

## Container Image

- **Registry:** `ghcr.io/bl4ck0z/sync-service:latest`
- **Auto-updates:** Every push to main branch
- **Platforms:** linux/amd64, linux/arm64

## License

MIT License - see [LICENSE](LICENSE)

---

For development documentation, see [dev/README.md](dev/README.md)