# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SLM (Slurm Lifecycle Monitor) is a low-coupling Python CLI tool for monitoring Slurm job lifecycle events. It provides zero-pollution monitoring by wrapping existing shell scripts without modifying the original logic. The system captures job events through webhook notifications and optionally logs them to a MySQL database.

## High-Level Architecture

The project follows a **two-layer decoupled design**:

1. **Submission Layer** (`slm submit`):
   - Sends "SUBMITTED" notification/webhook
   - Delegates to actual `sbatch` command
   - Captures submission failures

2. **Execution Layer** (`slm run`):
   - Wraps core logic of the job
   - Captures Slurm signals (suspend/resume/terminate via SIGTSTP/SIGCONT/SIGTERM)
   - Monitors exit status
   - Sends webhook notifications for all lifecycle events

### Core Components

- **`slm.py`**: Main SDK with CLI interface. Contains `SlmSDK` class that handles:
  - Signal detection (SIGTSTP, SIGCONT, SIGTERM, SIGINT)
  - Job lifecycle events: SUBMITTED, RUNNING, PAUSED, RESUMED, TERMINATING, COMPLETED, FAILED
  - Webhook notifications (via environment variable)

- **`database.py`**: MySQL integration for persistent job tracking with two tables:
  - `slurm_jobs`: Job metadata and current status
  - `slurm_events`: Detailed lifecycle event history
  - Graceful degradation if database unavailable

## Development Commands

### Installation
```bash
# Recommended: Using uv package manager
uv sync

# Alternative: Using pip
pip install -r requirements.txt
```

### Important: Always Use `uv run` for Python Commands

**CRITICAL:** All Python commands in this project MUST be executed using `uv run`. This ensures the correct virtual environment and dependencies are used.

```bash
# ✅ CORRECT - Use uv run for all Python commands
uv run python -m py_compile src/slurm_admin/slm.py
uv run python script.py
uv run slm submit job.sh
uv run slm run -- echo "test"

# ❌ WRONG - Never use python or python3 directly
python script.py          # Wrong! Uses system Python
python3 script.py         # Wrong! Uses system Python
python -m pytest          # Wrong! Uses system Python
```

### Testing
```bash
# Run local test suite (no Slurm cluster required)
./tests/test_slm.sh

# Test basic functionality
uv run slm run -- echo "Hello, Slurm!"

# Test signal handling (manual - requires second terminal)
uv run slm run -- bash -c 'echo "Starting..."; sleep 30; echo "Done"'
# Then in another terminal: kill -TSTP <pid>, kill -CONT <pid>, kill -TERM <pid>
```

### Usage Examples
```bash
# Submit job with notification
uv run slm submit job_script.sh

# Run command with monitoring
uv run slm run -- python script.py

# Run bash script with monitoring
uv run slm run -- bash script.sh

# Run inline bash with monitoring
uv run slm run -- bash <<'EOF'
set -e
python step1.py
python step2.py
EOF
```

## Configuration

### Environment Variables

```bash
# Webhook URL for notifications (optional)
export SLM_WEBHOOK="https://your-webhook-url.com"

# Database Configuration (optional - for MySQL logging)
export SLM_DB_HOST="licoded.site"
export SLM_DB_PORT="3306"
export SLM_DB_USER="slurm_admin_rw"
export SLM_DB_PASSWORD="your_password"
export SLM_DB_NAME="slurm_admin"
```

Both webhook and database are optional - the tool will work without them (with reduced functionality).

### Command-Line Arguments

```bash
# Disable database logging for a single run
uv run slm --no-db run -- python script.py
```

## Integration Patterns

The key design principle is **zero-pollution wrapping** - original scripts remain unchanged:

### Pattern 1: Direct Command
```bash
uv run slm run -- python train.py --epochs 100
```

### Pattern 2: Inline Bash (for multi-step jobs)
```bash
uv run slm run -- bash <<'EOF'
set -e
python download.py
python process.py
python upload.py
EOF
```

### Pattern 3: Job Script Integration
To add monitoring to existing Slurm scripts, wrap the core logic:

**Before:**
```bash
#!/bin/bash
#SBATCH -J my_script
#SBATCH -c 4

python process.py
./analyze.sh
```

**After (only 2 lines changed):**
```bash
#!/bin/bash
#SBATCH -J my_script
#SBATCH -c 4

uv run /path/to/slurm-admin/src/slurm_admin/slm.py run -- bash <<'EOF'
python process.py
./analyze.sh
EOF
```

## Key Design Concepts

1. **Signal Awareness**: SLM detects Slurm control signals automatically:
   - `SIGTSTP` (scontrol suspend) → PAUSED event
   - `SIGCONT` (scontrol resume) → RESUMED event
   - `SIGTERM` (scancel/timeout) → TERMINATING event
   - `SIGINT` (Ctrl+C) → TERMINATING event

2. **Graceful Degradation**: The tool continues working even if:
   - Database is unavailable (logs to stderr only)
   - Webhook is not configured (skips notifications)
   - pymysql is not installed (database features disabled)

3. **Environment Isolation**: All configuration through environment variables - no config files to manage.

4. **Low Coupling**: Easy to integrate and remove - just unwrap the `slm run` command.

## File Structure Notes

- `src/slurm_admin/`: Main source code
- `examples/`: Example Slurm job scripts demonstrating integration patterns
- `docs/`: Comprehensive documentation (QUICKSTART.md, DATABASE_SETUP.md, etc.)
- `scripts/query_jobs.py`: Utility for querying job status from database
- `sql/init_schema.sql`: Database schema (auto-created on first use)
- `tests/test_slm.sh`: Local test suite (no cluster required)

## Important Implementation Details

1. **Singleton Pattern**: Database connection uses singleton (`_db_instance`) to avoid multiple connections

2. **Exit Codes**: SLM preserves the original command's exit code for COMPLETED/FAILED status

3. **Signal Handler Logic**: Prevents duplicate logging of the same signal type using `signal_received["signal"]` check

4. **Database Tables**: Auto-created on first use via `ensure_tables()` method

5. **CLI Entry Point**: Defined in `pyproject.toml` as `[project.scripts]` section: `slm = "slurm_admin.slm:main"`
