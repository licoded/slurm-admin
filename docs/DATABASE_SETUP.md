# Database Setup Guide

This guide explains how to set up and use the MySQL database for tracking Slurm job lifecycle events.

## 📋 Prerequisites

- MySQL 5.7 or higher
- Database credentials (see `.env.example` for defaults)
- pymysql Python package

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
uv sync
```

This will install `pymysql` for database connectivity.

### 2. Initialize Database Schema

Connect to your MySQL server and run the initialization script:

```bash
mysql -h licoded.site -P 3306 -u slurm_admin_rw -p < sql/init_schema.sql
```

Enter password when prompted: `Slurm@Admin2026#RW`

Or from within MySQL client:

```bash
mysql -h licoded.site -P 3306 -u slurm_admin_rw -p
```

Then run:

```sql
source sql/init_schema.sql
```

### 3. Configure Environment Variables

The default configuration is already set in `.env.example`:

```bash
# Database Configuration
SLM_DB_HOST="licoded.site"
SLM_DB_PORT="3306"
SLM_DB_USER="slurm_admin_rw"
SLM_DB_PASSWORD="Slurm@Admin2026#RW"
SLM_DB_NAME="slurm_admin"
```

You can override these by:

1. Creating a `.env.local` file (recommended)
2. Setting environment variables in your shell
3. Using CLI arguments with `slm` commands

### 4. Test Database Connection

```bash
# Test with slm query command
uv run slm query

# Or use the query script
uv run python scripts/query_jobs.py --recent
```

## 📊 Database Schema

### Tables

#### `slurm_jobs`
Stores job metadata and current status.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT | Auto-increment primary key |
| job_id | VARCHAR(128) | Slurm Job ID (unique) |
| job_name | VARCHAR(255) | Job name from #SBATCH -J |
| script_path | TEXT | Path to job script |
| command | TEXT | Command executed |
| nodes | VARCHAR(128) | Node allocation |
| cpus | VARCHAR(32) | CPU count |
| gpus | VARCHAR(32) | GPU allocation |
| memory | VARCHAR(32) | Memory allocation |
| partition | VARCHAR(64) | Slurm partition |
| submitted_at | DATETIME | Submission time |
| started_at | DATETIME | Start time |
| completed_at | DATETIME | Completion time |
| status | VARCHAR(32) | Current status |
| exit_code | INT | Process exit code |
| created_at | TIMESTAMP | Record creation |
| updated_at | TIMESTAMP | Last update |

#### `slurm_events`
Stores lifecycle events for each job.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT | Auto-increment primary key |
| job_id | VARCHAR(128) | Slurm Job ID (foreign key) |
| event_type | VARCHAR(32) | Event type (lifecycle, signal, etc.) |
| event_status | VARCHAR(32) | Event status |
| details | TEXT | Event description |
| metadata | JSON | Additional metadata |
| created_at | TIMESTAMP | Event timestamp |

### Views

#### `v_recent_jobs`
Summary view of recent jobs with duration and event count.

#### `v_job_stats`
Aggregated statistics by status.

## 🔧 Usage

### With SLM Commands

Database logging is **enabled by default**. All lifecycle events are automatically recorded.

```bash
# Submit job (automatically records to database)
uv run slm submit job_script.sh

# Run command (automatically records events)
uv run slm run -- python train.py

# Query job information
uv run slm query <job_id>
uv run slm query --events
```

### Disable Database Logging

If you want to disable database logging for a specific command:

```bash
uv run slm --no-db run -- python script.py
```

### Using Different Database Credentials

Configure database connection via environment variables:

```bash
export SLM_DB_HOST="localhost"
export SLM_DB_USER="root"
export SLM_DB_PASSWORD="secret"
export SLM_DB_NAME="my_slurm_db"

uv run slm run -- python script.py
```

## 📈 Query Examples

### Using the Query Script

```bash
# Show recent jobs
uv run python scripts/query_jobs.py --recent 20

# Show specific job details
uv run python scripts/query_jobs.py --job-id 12345

# Show running jobs
uv run python scripts/query_jobs.py --status RUNNING

# Show failed jobs
uv run python scripts/query_jobs.py --status FAILED

# Show statistics
uv run python scripts/query_jobs.py --stats
```

### Direct SQL Queries

Connect to the database:

```bash
mysql -h licoded.site -P 3306 -u slurm_admin_rw -p slurm_admin
```

Example queries:

```sql
-- Show all jobs from today
SELECT * FROM slurm_jobs
WHERE DATE(submitted_at) = CURDATE()
ORDER BY submitted_at DESC;

-- Show jobs with exit code != 0
SELECT job_id, job_name, exit_code, completed_at
FROM slurm_jobs
WHERE exit_code != 0
ORDER BY completed_at DESC;

-- Show average job duration by partition
SELECT
  partition,
  AVG(TIMESTAMPDIFF(SECOND, started_at, completed_at)) as avg_duration
FROM slurm_jobs
WHERE started_at IS NOT NULL AND completed_at IS NOT NULL
GROUP BY partition;

-- Show event timeline for a job
SELECT event_type, event_status, details, created_at
FROM slurm_events
WHERE job_id = '12345'
ORDER BY created_at;

-- Show jobs that ran longer than expected
SELECT job_id, job_name,
  TIMESTAMPDIFF(HOUR, started_at, completed_at) as hours
FROM slurm_jobs
WHERE started_at IS NOT NULL
  AND completed_at IS NOT NULL
  AND TIMESTAMPDIFF(HOUR, started_at, completed_at) > 24
ORDER BY hours DESC;
```

## 🔍 Monitoring and Debugging

### Check if Database is Working

```bash
# Check recent entries
uv run python scripts/query_jobs.py --recent 5

# Check if your job was recorded
uv run slm query $SLURM_JOB_ID
```

### View All Events for a Job

```bash
uv run slm query --events
```

Or via SQL:

```sql
SELECT * FROM slurm_events WHERE job_id = 'YOUR_JOB_ID' ORDER BY created_at;
```

## 🔐 Security Considerations

1. **Password Security**: The default credentials are in `.env.example`. For production:
   - Use environment variables or secure credential management
   - Don't commit `.env.local` to version control
   - Use read-only database users for querying

2. **Database Permissions**: The `slurm_admin_rw` user has read-write access. For monitoring-only access, create a read-only user:

```sql
CREATE USER 'slurm_admin_ro'@'%' IDENTIFIED BY 'readonly_password';
GRANT SELECT ON slurm_admin.* TO 'slurm_admin_ro'@'%';
FLUSH PRIVILEGES;
```

3. **Network Security**: If the database is accessible over the network:
   - Use SSL connections
   - Restrict access by IP
   - Use a VPN or SSH tunnel

## 🛠️ Troubleshooting

### Connection Issues

**Error**: `Can't connect to MySQL server`

**Solutions**:
1. Check network connectivity: `ping licoded.site`
2. Verify MySQL is running: `systemctl status mysql`
3. Check firewall rules
4. Verify credentials

**Error**: `Access denied for user`

**Solutions**:
1. Verify username and password
2. Check user permissions: `SHOW GRANTS FOR 'slurm_admin_rw'@'%';`
3. Ensure user has access from your host

### Table Issues

**Error**: `Table 'slurm_admin.slurm_jobs' doesn't exist`

**Solution**: Run the schema initialization script:
```bash
mysql -h licoded.site -u slurm_admin_rw -p < sql/init_schema.sql
```

### Performance Issues

For high-volume environments:

1. Add indexes for common queries
2. Archive old jobs to a separate table
3. Use partitioning by date
4. Regularly clean up old events

```sql
-- Archive jobs older than 90 days
CREATE TABLE slurm_jobs_archive LIKE slurm_jobs;

INSERT INTO slurm_jobs_archive
SELECT * FROM slurm_jobs
WHERE completed_at < DATE_SUB(NOW(), INTERVAL 90 DAY);

DELETE FROM slurm_jobs
WHERE completed_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
```

## 📚 Next Steps

1. Set up automated backups
2. Create monitoring dashboards
3. Set up alerts for failed jobs
4. Integrate with your existing monitoring tools
5. Create custom views for your specific needs

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the main README.md
3. Check database logs: `/var/log/mysql/error.log`
