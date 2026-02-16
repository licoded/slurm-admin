#!/usr/bin/env python3
"""
Query script for Slurm job database
Useful for monitoring and debugging
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add src directory to path to import database module
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

try:
    from slurm_admin.database import get_database, close_database, DatabaseConfig
except ImportError as e:
    print(f"Error: Could not import database module: {e}", file=sys.stderr)
    sys.exit(1)


def print_separator(char='-', length=80):
    print(char * length)


def print_job_info(job):
    """Print job information in a readable format"""
    print_separator()
    print(f"Job ID:         {job.get('job_id', 'N/A')}")
    print(f"Job Name:       {job.get('job_name', 'N/A')}")
    print(f"Status:         {job.get('status', 'N/A')}")
    print(f"Partition:      {job.get('partition_name', 'N/A')}")
    print(f"Nodes:          {job.get('nodes', 'N/A')}")
    print(f"CPUs:           {job.get('cpus', 'N/A')}")
    print(f"GPUs:           {job.get('gpus', 'N/A')}")
    print(f"Memory:         {job.get('memory', 'N/A')}")
    print(f"Submitted:      {job.get('submitted_at', 'N/A')}")
    print(f"Started:        {job.get('started_at', 'N/A')}")
    print(f"Completed:      {job.get('completed_at', 'N/A')}")
    print(f"Exit Code:      {job.get('exit_code', 'N/A')}")
    print(f"Script:         {job.get('script_path', 'N/A')}")
    print(f"Command:        {job.get('command', 'N/A')[:100]}{'...' if len(job.get('command', '')) > 100 else ''}")


def print_event_info(event):
    """Print event information in a readable format"""
    timestamp = event.get('created_at', 'N/A')
    event_type = event.get('event_type', 'N/A')
    event_status = event.get('event_status', 'N/A')
    details = event.get('details', '')[:60]
    print(f"  {timestamp} | {event_type:15} | {event_status:12} | {details}")


def query_recent_jobs(db, limit=20):
    """Query and display recent jobs"""
    print(f"\nRecent {limit} Jobs:")
    print_separator()

    try:
        with db.connection.cursor() as cursor:
            query = """
                SELECT job_id, job_name, status, partition_name,
                       submitted_at, started_at, completed_at, exit_code
                FROM slurm_jobs
                ORDER BY created_at DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            jobs = cursor.fetchall()

            if jobs:
                print(f"{'Job ID':<15} | {'Name':<25} | {'Status':<12} | {'Submitted':<20}")
                print_separator()
                for job in jobs:
                    job_id = job.get('job_id', 'N/A')[:15]
                    job_name = job.get('job_name', 'N/A')[:25]
                    status = job.get('status', 'N/A')[:12]
                    submitted = str(job.get('submitted_at', 'N/A'))[:20]
                    print(f"{job_id:<15} | {job_name:<25} | {status:<12} | {submitted:<20}")
            else:
                print("No jobs found")

    except Exception as e:
        print(f"Error querying jobs: {e}", file=sys.stderr)


def query_job_details(db, job_id):
    """Query and display detailed information for a specific job"""
    job_info = db.get_job_info(job_id)

    if not job_info:
        print(f"No information found for job {job_id}")
        return

    print_job_info(job_info)

    # Show events
    print(f"\nEvents for job {job_id}:")
    print_separator()
    events = db.get_job_events(job_id, limit=50)
    if events:
        for event in events:
            print_event_info(event)
    else:
        print("  No events found")


def query_jobs_by_status(db, status, limit=20):
    """Query jobs by status"""
    print(f"\nJobs with status '{status}':")
    print_separator()

    try:
        with db.connection.cursor() as cursor:
            query = """
                SELECT job_id, job_name, status, partition_name,
                       submitted_at, started_at, completed_at
                FROM slurm_jobs
                WHERE status = %s
                ORDER BY submitted_at DESC
                LIMIT %s
            """
            cursor.execute(query, (status, limit))
            jobs = cursor.fetchall()

            if jobs:
                for job in jobs:
                    print_job_info(job)
                    print()
            else:
                print(f"No jobs found with status '{status}'")

    except Exception as e:
        print(f"Error querying jobs: {e}", file=sys.stderr)


def query_job_statistics(db):
    """Query and display job statistics"""
    print("\nJob Statistics:")
    print_separator()

    try:
        with db.connection.cursor() as cursor:
            # Status distribution
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM slurm_jobs
                GROUP BY status
                ORDER BY count DESC
            """)
            stats = cursor.fetchall()

            print("Status Distribution:")
            for stat in stats:
                status = stat.get('status', 'N/A')
                count = stat.get('count', 0)
                print(f"  {status:<15}: {count:>5} jobs")

            print_separator()

            # Success/failure rate
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as failed
                FROM slurm_jobs
                WHERE completed_at IS NOT NULL
            """)
            result = cursor.fetchone()

            if result:
                total = result.get('total', 0)
                success = result.get('success', 0)
                failed = result.get('failed', 0)

                print("Completion Statistics:")
                print(f"  Total completed: {total}")
                print(f"  Successful:      {success} ({success*100//total if total > 0 else 0}%)")
                print(f"  Failed:          {failed} ({failed*100//total if total > 0 else 0}%)")

            print_separator()

            # Average duration
            cursor.execute("""
                SELECT
                  AVG(TIMESTAMPDIFF(SECOND, started_at, completed_at)) as avg_duration,
                  MIN(TIMESTAMPDIFF(SECOND, started_at, completed_at)) as min_duration,
                  MAX(TIMESTAMPDIFF(SECOND, started_at, completed_at)) as max_duration
                FROM slurm_jobs
                WHERE started_at IS NOT NULL AND completed_at IS NOT NULL
            """)
            result = cursor.fetchone()

            if result and result.get('avg_duration'):
                avg_sec = result.get('avg_duration', 0)
                min_sec = result.get('min_duration', 0)
                max_sec = result.get('max_duration', 0)

                def format_duration(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    return f"{hours}h {minutes}m {secs}s"

                print("Duration Statistics:")
                print(f"  Average: {format_duration(avg_sec)}")
                print(f"  Minimum: {format_duration(min_sec)}")
                print(f"  Maximum: {format_duration(max_sec)}")

    except Exception as e:
        print(f"Error querying statistics: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Query Slurm job database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show recent jobs
  python query_jobs.py --recent

  # Show details for a specific job
  python query_jobs.py --job-id 12345

  # Show all running jobs
  python query_jobs.py --status RUNNING

  # Show failed jobs
  python query_jobs.py --status FAILED

  # Show job statistics
  python query_jobs.py --stats
        """
    )

    parser.add_argument('--recent', type=int, metavar='N',
                       help='Show N most recent jobs')
    parser.add_argument('--job-id', metavar='ID',
                       help='Show details for specific job ID')
    parser.add_argument('--status', metavar='STATUS',
                       choices=['SUBMITTED', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'TERMINATING'],
                       help='Show jobs with specific status')
    parser.add_argument('--stats', action='store_true',
                       help='Show job statistics')
    parser.add_argument('--db-host', metavar='HOST',
                       help='Database host (overrides SLM_DB_HOST)')
    parser.add_argument('--db-port', type=int, metavar='PORT',
                       help='Database port (overrides SLM_DB_PORT)')
    parser.add_argument('--db-user', metavar='USER',
                       help='Database user (overrides SLM_DB_USER)')
    parser.add_argument('--db-password', metavar='PASS',
                       help='Database password (overrides SLM_DB_PASSWORD)')
    parser.add_argument('--db-name', metavar='NAME',
                       help='Database name (overrides SLM_DB_NAME)')

    args = parser.parse_args()

    # Set database environment variables from CLI args
    if args.db_host:
        os.environ['SLM_DB_HOST'] = args.db_host
    if args.db_port:
        os.environ['SLM_DB_PORT'] = str(args.db_port)
    if args.db_user:
        os.environ['SLM_DB_USER'] = args.db_user
    if args.db_password:
        os.environ['SLM_DB_PASSWORD'] = args.db_password
    if args.db_name:
        os.environ['SLM_DB_NAME'] = args.db_name

    try:
        # Connect to database
        config = DatabaseConfig()
        db = SlurmDatabase(config)
        db.ensure_tables()

        # Execute query
        if args.stats:
            query_job_statistics(db)
        elif args.job_id:
            query_job_details(db, args.job_id)
        elif args.status:
            query_jobs_by_status(db, args.status)
        elif args.recent:
            query_recent_jobs(db, limit=args.recent)
        else:
            # Default: show recent 10 jobs
            query_recent_jobs(db, limit=10)

        # Close connection
        db.disconnect()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Import SlurmDatabase here to avoid circular import
    from database import SlurmDatabase
    main()
