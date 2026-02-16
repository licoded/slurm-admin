-- Slurm Lifecycle Monitor Database Schema
-- MySQL 5.7+ compatible
-- This script creates the necessary tables for tracking Slurm jobs and events

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS slurm_admin
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE slurm_admin;

-- Drop tables if they exist (for clean reinstall)
-- DROP TABLE IF EXISTS slurm_events;
-- DROP TABLE IF EXISTS slurm_jobs;

-- Create slurm_jobs table
-- Stores job metadata and current status
CREATE TABLE IF NOT EXISTS slurm_jobs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
  job_id VARCHAR(128) NOT NULL UNIQUE COMMENT 'Slurm Job ID',
  job_name VARCHAR(255) NOT NULL COMMENT 'Job name from#SBATCH -J',
  script_path TEXT COMMENT 'Absolute path to job script',
  command TEXT COMMENT 'Command executed by slm run',
  nodes VARCHAR(128) COMMENT 'Node list from SLURM_JOB_NODELIST',
  cpus VARCHAR(32) COMMENT 'CPU count from SLURM_CPUS_PER_TASK',
  gpus VARCHAR(32) COMMENT 'GPU allocation from SLURM_JOB_GRES',
  memory VARCHAR(32) COMMENT 'Memory from SLURM_MEM_PER_NODE',
  partition_name VARCHAR(64) COMMENT 'Partition from SLURM_JOB_PARTITION',
  submitted_at DATETIME COMMENT 'Job submission time',
  started_at DATETIME COMMENT 'Job start time',
  completed_at DATETIME COMMENT 'Job completion time',
  status VARCHAR(32) COMMENT 'Current status: SUBMITTED, RUNNING, PAUSED, RESUMED, TERMINATING, COMPLETED, FAILED',
  exit_code INT COMMENT 'Process exit code',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update time',

  INDEX idx_job_id (job_id),
  INDEX idx_status (status),
  INDEX idx_submitted_at (submitted_at),
  INDEX idx_completed_at (completed_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Slurm job tracking table';

-- Create slurm_events table
-- Stores lifecycle events for each job
CREATE TABLE IF NOT EXISTS slurm_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
  job_id VARCHAR(128) NOT NULL COMMENT 'Slurm Job ID',
  event_type VARCHAR(32) NOT NULL COMMENT 'Event type: lifecycle, signal, error, etc.',
  event_status VARCHAR(32) NOT NULL COMMENT 'Event status: SUBMITTED, RUNNING, PAUSED, etc.',
  details TEXT COMMENT 'Event description',
  metadata JSON COMMENT 'Additional event metadata',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Event timestamp',

  INDEX idx_job_id (job_id),
  INDEX idx_event_type (event_type),
  INDEX idx_event_status (event_status),
  INDEX idx_created_at (created_at),
  FOREIGN KEY (job_id) REFERENCES slurm_jobs(job_id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Slurm job event log table';

-- Create a view for recent job summary
CREATE OR REPLACE VIEW v_recent_jobs AS
SELECT
  j.job_id,
  j.job_name,
  j.status,
  j.partition_name as partition,
  j.nodes,
  j.cpus,
  j.gpus,
  j.memory,
  j.submitted_at,
  j.started_at,
  j.completed_at,
  j.exit_code,
  TIMESTAMPDIFF(SECOND, j.started_at, j.completed_at) as duration_seconds,
  (SELECT COUNT(*) FROM slurm_events e WHERE e.job_id = j.job_id) as event_count,
  j.updated_at
FROM slurm_jobs j
WHERE j.submitted_at IS NOT NULL
ORDER BY j.submitted_at DESC;

-- Create a view for job statistics
CREATE OR REPLACE VIEW v_job_stats AS
SELECT
  status,
  COUNT(*) as job_count,
  SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) as success_count,
  SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as failure_count,
  AVG(CASE
    WHEN started_at IS NOT NULL AND completed_at IS NOT NULL
    THEN TIMESTAMPDIFF(SECOND, started_at, completed_at)
    ELSE NULL
  END) as avg_duration_seconds
FROM slurm_jobs
GROUP BY status;

-- Sample queries
-- Show all jobs:
--   SELECT * FROM slurm_jobs ORDER BY submitted_at DESC;
--
-- Show recent jobs summary:
--   SELECT * FROM v_recent_jobs LIMIT 20;
--
-- Show job statistics:
--   SELECT * FROM v_job_stats;
--
-- Show events for a specific job:
--   SELECT * FROM slurm_events WHERE job_id = '12345' ORDER BY created_at;
--
-- Show failed jobs:
--   SELECT * FROM slurm_jobs WHERE status = 'FAILED' ORDER BY submitted_at DESC;
--
-- Show running jobs:
--   SELECT * FROM slurm_jobs WHERE status = 'RUNNING' ORDER BY submitted_at DESC;
