#!/usr/bin/env python3
"""
Database module for Slurm Lifecycle Monitor
Handles MySQL connection and data persistence
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None
    print("[SLM.DB] Warning: 'pymysql' module not found. Database logging will be disabled.", file=sys.stderr)


class DatabaseConfig:
    """Database configuration from environment variables"""

    def __init__(self):
        self.host = os.getenv("SLM_DB_HOST", "licoded.site")
        self.port = int(os.getenv("SLM_DB_PORT", "3306"))
        self.user = os.getenv("SLM_DB_USER", "slurm_admin_rw")
        self.password = os.getenv("SLM_DB_PASSWORD", "Slurm@Admin2026#RW")
        self.database = os.getenv("SLM_DB_NAME", "slurm_admin")
        self.charset = "utf8mb4"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'charset': self.charset,
            'cursorclass': DictCursor
        }


class SlurmDatabase:
    """Database manager for Slurm job tracking"""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.connection = None
        self.enabled = pymysql is not None

        if not self.enabled:
            return

        try:
            self.connect()
        except Exception as e:
            print(f"[SLM.DB] Failed to connect to database: {e}", file=sys.stderr)
            print(f"[SLM.DB] Database logging disabled", file=sys.stderr)
            self.enabled = False

    def connect(self):
        """Establish database connection"""
        if not pymysql:
            return

        try:
            self.connection = pymysql.connect(**self.config.to_dict())
            print(f"[SLM.DB] Connected to MySQL at {self.config.host}:{self.config.port}", file=sys.stderr)
        except Exception as e:
            raise Exception(f"Connection failed: {e}")

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def ensure_tables(self):
        """Create tables if they don't exist"""
        if not self.enabled or not self.connection:
            return

        try:
            with self.connection.cursor() as cursor:
                # Create slurm_jobs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS slurm_jobs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        job_id VARCHAR(128) NOT NULL UNIQUE,
                        job_name VARCHAR(255) NOT NULL,
                        script_path TEXT,
                        command TEXT,
                        nodes VARCHAR(128),
                        cpus VARCHAR(32),
                        gpus VARCHAR(32),
                        memory VARCHAR(32),
                        partition_name VARCHAR(64),
                        submitted_at DATETIME,
                        started_at DATETIME,
                        completed_at DATETIME,
                        status VARCHAR(32),
                        exit_code INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_job_id (job_id),
                        INDEX idx_status (status),
                        INDEX idx_submitted_at (submitted_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                # Create slurm_events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS slurm_events (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        job_id VARCHAR(128) NOT NULL,
                        event_type VARCHAR(32) NOT NULL,
                        event_status VARCHAR(32) NOT NULL,
                        details TEXT,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_job_id (job_id),
                        INDEX idx_event_type (event_type),
                        INDEX idx_created_at (created_at),
                        FOREIGN KEY (job_id) REFERENCES slurm_jobs(job_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                self.connection.commit()
                print("[SLM.DB] Tables verified/created", file=sys.stderr)

        except Exception as e:
            print(f"[SLM.DB] Failed to create tables: {e}", file=sys.stderr)
            raise

    def register_job(self, job_id: str, job_name: str, **kwargs) -> Optional[int]:
        """Register a new job in the database"""
        if not self.enabled or not self.connection:
            return None

        try:
            with self.connection.cursor() as cursor:
                # Check if job already exists
                cursor.execute("SELECT id FROM slurm_jobs WHERE job_id = %s", (job_id,))
                if cursor.fetchone():
                    # Update existing job
                    update_fields = []
                    update_values = []

                    for key, value in kwargs.items():
                        if value is not None:
                            update_fields.append(f"{key} = %s")
                            update_values.append(value)

                    if update_fields:
                        update_values.append(job_id)
                        update_query = f"UPDATE slurm_jobs SET {', '.join(update_fields)} WHERE job_id = %s"
                        cursor.execute(update_query, update_values)
                else:
                    # Insert new job
                    columns = ['job_id', 'job_name'] + [k for k, v in kwargs.items() if v is not None]
                    values = [job_id, job_name] + [v for k, v in kwargs.items() if v is not None]
                    placeholders = ', '.join(['%s'] * len(columns))

                    insert_query = f"""
                        INSERT INTO slurm_jobs ({', '.join(columns)})
                        VALUES ({placeholders})
                    """
                    cursor.execute(insert_query, values)

                self.connection.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"[SLM.DB] Failed to register job: {e}", file=sys.stderr)
            return None

    def update_job_status(self, job_id: str, status: str, **kwargs) -> bool:
        """Update job status and other fields"""
        if not self.enabled or not self.connection:
            return False

        try:
            with self.connection.cursor() as cursor:
                update_fields = ["status = %s"]
                update_values = [status]

                # Map status to timestamp fields
                status_time_map = {
                    "SUBMITTED": "submitted_at",
                    "RUNNING": "started_at",
                    "COMPLETED": "completed_at",
                    "FAILED": "completed_at",
                    "TERMINATING": "completed_at"
                }

                if status in status_time_map:
                    timestamp_field = status_time_map[status]
                    update_fields.append(f"{timestamp_field} = %s")
                    update_values.append(datetime.now())

                for key, value in kwargs.items():
                    if value is not None:
                        update_fields.append(f"{key} = %s")
                        update_values.append(value)

                update_values.append(job_id)
                update_query = f"UPDATE slurm_jobs SET {', '.join(update_fields)} WHERE job_id = %s"

                cursor.execute(update_query, update_values)
                self.connection.commit()
                return True

        except Exception as e:
            print(f"[SLM.DB] Failed to update job status: {e}", file=sys.stderr)
            return False

    def log_event(self, job_id: str, event_type: str, event_status: str,
                  details: str = "", metadata: Optional[Dict] = None) -> Optional[int]:
        """Log a lifecycle event for a job"""
        if not self.enabled or not self.connection:
            return None

        try:
            with self.connection.cursor() as cursor:
                metadata_json = json.dumps(metadata) if metadata else None

                insert_query = """
                    INSERT INTO slurm_events (job_id, event_type, event_status, details, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """

                cursor.execute(insert_query, (job_id, event_type, event_status, details, metadata_json))
                self.connection.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"[SLM.DB] Failed to log event: {e}", file=sys.stderr)
            return None

    def get_job_events(self, job_id: str, limit: int = 100) -> list:
        """Retrieve events for a specific job"""
        if not self.enabled or not self.connection:
            return []

        try:
            with self.connection.cursor() as cursor:
                query = """
                    SELECT event_type, event_status, details, metadata, created_at
                    FROM slurm_events
                    WHERE job_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """
                cursor.execute(query, (job_id, limit))
                return cursor.fetchall()

        except Exception as e:
            print(f"[SLM.DB] Failed to get job events: {e}", file=sys.stderr)
            return []

    def get_job_info(self, job_id: str) -> Optional[Dict]:
        """Retrieve job information"""
        if not self.enabled or not self.connection:
            return None

        try:
            with self.connection.cursor() as cursor:
                query = "SELECT * FROM slurm_jobs WHERE job_id = %s"
                cursor.execute(query, (job_id,))
                return cursor.fetchone()

        except Exception as e:
            print(f"[SLM.DB] Failed to get job info: {e}", file=sys.stderr)
            return None


# Singleton instance
_db_instance: Optional[SlurmDatabase] = None


def get_database() -> Optional[SlurmDatabase]:
    """Get or create database singleton instance"""
    global _db_instance

    if _db_instance is None and pymysql is not None:
        try:
            config = DatabaseConfig()
            _db_instance = SlurmDatabase(config)
            _db_instance.ensure_tables()
        except Exception as e:
            print(f"[SLM.DB] Failed to initialize database: {e}", file=sys.stderr)
            _db_instance = None

    return _db_instance


def close_database():
    """Close database connection"""
    global _db_instance

    if _db_instance:
        _db_instance.disconnect()
        _db_instance = None
