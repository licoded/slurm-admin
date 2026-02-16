#!/usr/bin/env python3
"""
Slurm Lifecycle Monitor (SLM) SDK
A low-coupling monitoring solution for Slurm job lifecycle management
"""

import os
import sys
import signal
import subprocess
import argparse
import re
from uuid import uuid4
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from .database import get_database, close_database
except ImportError:
    try:
        from database import get_database, close_database
    except ImportError:
        print("[SLM] Warning: 'database' module not found. Database logging will be disabled.", file=sys.stderr)
        get_database = None
        close_database = None

try:
    from .http_client import get_http_client
except ImportError:
    try:
        from http_client import get_http_client
    except ImportError:
        print("[SLM] Warning: 'http_client' module not found. HTTP logging will be disabled.", file=sys.stderr)
        get_http_client = None


class SlmSDK:
    """Slurm Lifecycle Monitor SDK"""

    def __init__(self, db_enabled: bool = True):
        self.job_id = os.getenv('SLURM_JOB_ID', 'N/A')
        self.job_name = os.getenv('SLURM_JOB_NAME', 'LocalTask')
        self.job_nodes = os.getenv('SLURM_JOB_NODELIST', 'N/A')
        self.job_cpus = os.getenv('SLURM_CPUS_PER_TASK', 'N/A')
        self.job_gpus = os.getenv('SLURM_JOB_GRES', 'N/A')
        self.job_mem = os.getenv('SLURM_MEM_PER_NODE', 'N/A')
        self.job_partition = os.getenv('SLURM_JOB_PARTITION', 'N/A')

        # Determine execution environment
        self.is_compute_node = bool(os.getenv('SLURM_JOB_ID'))

        # Initialize: Use database on login node, HTTP client on compute node
        if self.is_compute_node:
            # Compute node: Use HTTP client
            self.db = None
            self.http = get_http_client() if get_http_client else None
            if self.http:
                print(f"[SLM] Compute node detected: Using HTTP API for logging", file=sys.stderr)
            else:
                print(f"[SLM] Compute node: HTTP client unavailable, logging disabled", file=sys.stderr)
        else:
            # Login node: Use database directly
            self.db = get_database() if (db_enabled and get_database) else None
            self.http = None
            if self.db:
                print(f"[SLM.DB] Login node: Database logging enabled", file=sys.stderr)
            else:
                print(f"[SLM] Login node: Database unavailable", file=sys.stderr)

    def _log_event(self, event_type: str, event_status: str, details: str = "", metadata: Optional[Dict] = None):
        """Log event to database or via HTTP API"""
        if self.db:
            self.db.log_event(self.job_id, event_type, event_status, details, metadata)
        elif self.http:
            self.http.log_event(self.job_id, event_type, event_status, details, metadata)

    def _update_job_status(self, status: str, **kwargs):
        """Update job status in database or via HTTP API"""
        if self.db:
            return self.db.update_job_status(self.job_id, status, **kwargs)
        elif self.http:
            return self.http.update_job_status(self.job_id, status, **kwargs)
        return False

    def log_status(self, status: str, details: str = ""):
        """Log status to database"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._log_event("lifecycle", status, details, {"timestamp": now})
        print(f"[SLM] {status}: {details}", file=sys.stderr)

    def register_job(self, script_path: str = None, command: str = None, submission_source: str = None):
        """Register job in database or via HTTP API"""
        job_data = {
            'script_path': script_path,
            'command': command,
            'nodes': self.job_nodes,
            'cpus': self.job_cpus,
            'gpus': self.job_gpus,
            'memory': self.job_mem,
            'partition_name': self.job_partition,
            'status': 'SUBMITTED'
        }

        if self.db:
            self.db.register_job(self.job_id, self.job_name, submission_source=submission_source, **job_data)
        elif self.http:
            self.http.register_job(self.job_id, self.job_name, submission_source=submission_source, **job_data)

    def monitor_run(self, cmd_args: List[str]):
        """Core monitoring logic: wrap and execute the actual command"""
        if not cmd_args:
            print("[SLM] Error: No command provided to run", file=sys.stderr)
            sys.exit(1)

        cmd_str = ' '.join(cmd_args)
        print(f"[SLM] Starting command: {cmd_str}")

        # Determine job_id based on execution environment (Approach A: Explicit)
        slurm_job_id = os.getenv('SLURM_JOB_ID')

        if slurm_job_id:
            # Scenario 1 & 2: Slurm environment
            self.job_id = f"slurm-{slurm_job_id}"

            # Update resource fields from actual Slurm environment
            self.job_nodes = os.getenv('SLURM_JOB_NODELIST', 'N/A')
            self.job_cpus = os.getenv('SLURM_CPUS_PER_TASK', os.getenv('SLURM_CPUS_ON_NODE', 'N/A'))
            self.job_gpus = os.getenv('SLURM_JOB_GRES', 'N/A')
            # Try multiple memory-related env vars
            self.job_mem = os.getenv('SLURM_MEM_PER_NODE') or os.getenv('SLURM_MEM_PER_CPU', 'N/A')
            if self.job_mem != 'N/A' and os.getenv('SLURM_MEM_PER_CPU'):
                # If we have per-CPU memory, calculate total memory
                cpus = int(self.job_cpus) if self.job_cpus != 'N/A' else 1
                try:
                    self.job_mem = f"{int(self.job_mem) * cpus}MB"
                except:
                    pass
            self.job_partition = os.getenv('SLURM_JOB_PARTITION', 'N/A')

            # Try to update existing record (Scenario 1: user used slm submit)
            updated = self._update_job_status("RUNNING",
                                               command=cmd_str,
                                               nodes=self.job_nodes,
                                               cpus=self.job_cpus,
                                               gpus=self.job_gpus,
                                               memory=self.job_mem,
                                               partition_name=self.job_partition)

            if not updated:
                # Scenario 2: No record found (user used sbatch directly)
                print("[SLM] No submission record found, creating new entry (direct_sbatch)", file=sys.stderr)
                self.register_job(command=cmd_str, submission_source='direct_sbatch')
                # Update with resource fields
                self._update_job_status("RUNNING",
                                       command=cmd_str,
                                       nodes=self.job_nodes,
                                       cpus=self.job_cpus,
                                       gpus=self.job_gpus,
                                       memory=self.job_mem,
                                       partition_name=self.job_partition)
            # else: Scenario 1: Record found and updated
        else:
            # Scenario 3: Local test environment
            self.job_id = f"raw-{uuid4()}"
            print(f"[SLM] Local test mode, job_id: {self.job_id}", file=sys.stderr)
            self.register_job(command=cmd_str, submission_source='local_test')
            self._update_job_status("RUNNING", command=cmd_str)

        self.log_status("RUNNING", f"Command: {cmd_str}")

        # Signal handling
        signal_received = {"signal": None}

        def handle_signal(signum, frame):
            sig_map = {
                signal.SIGTSTP: "PAUSED",
                signal.SIGCONT: "RESUMED",
                signal.SIGTERM: "TERMINATING",
                signal.SIGINT: "TERMINATING"
            }
            status = sig_map.get(signum, f"SIGNAL_{signum}")
            signal_name = signal.Signals(signum).name

            # Only log for first occurrence of each signal type
            if signal_received["signal"] != status:
                signal_received["signal"] = status
                self._update_job_status(status)
                self.log_status(status, f"Received signal: {signal_name}")

                if status == "TERMINATING":
                    print(f"[SLM] Received {signal_name}, terminating...", file=sys.stderr)
                    if self.db:
                        close_database()
                    sys.exit(143)  # Standard exit code for SIGTERM

        # Register signal handlers for Slurm-related signals
        signal.signal(signal.SIGTSTP, handle_signal)  # scontrol suspend
        signal.signal(signal.SIGCONT, handle_signal)  # scontrol resume
        signal.signal(signal.SIGTERM, handle_signal)  # scancel/timeout
        signal.signal(signal.SIGINT, handle_signal)   # Ctrl+C

        try:
            # Execute subprocess
            process = subprocess.Popen(cmd_args)
            exit_code = process.wait()

            # Final notification
            if exit_code == 0:
                final_status = "COMPLETED"
                details = "Job completed successfully"
            else:
                final_status = "FAILED"
                details = f"Exit code: {exit_code}"

            self._update_job_status(final_status, exit_code=exit_code)
            self.log_status(final_status, details)

            # Close database connection before exit
            if self.db:
                close_database()

            sys.exit(exit_code)

        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            print(f"[SLM] {error_msg}", file=sys.stderr)

            self._update_job_status("FAILED")
            self.log_status("FAILED", error_msg)

            if self.db:
                close_database()

            sys.exit(1)


def main():
    """Main entry point for SLM CLI"""
    parser = argparse.ArgumentParser(
        description="Slurm Lifecycle Monitor SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit a job script
  ./slm submit job_script.sh

  # Run a command with monitoring
  ./slm run -- /public/home/jwli/python3/bin/python3 train.py --epochs 100

  # Query job information
  ./slm query

  # Disable database logging
  ./slm --no-db run -- /public/home/jwli/python3/bin/python3 script.py

Environment Variables:
  SLM_DB_HOST       Database host (default: licoded.site)
  SLM_DB_PORT       Database port (default: 3306)
  SLM_DB_USER       Database user (default: slurm_admin_rw)
  SLM_DB_PASSWORD   Database password (default: Slurm@Admin2026#RW)
  SLM_DB_NAME       Database name (default: slurm_admin)
        """
    )

    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Disable database logging'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Submit subcommand
    submit_parser = subparsers.add_parser('submit', help='Submit a job to Slurm with notification')
    submit_parser.add_argument('script', help='The .sh script to submit')
    submit_parser.add_argument(
        '--sbatch-args',
        default='',
        help='Additional arguments to pass to sbatch'
    )

    # Run subcommand
    run_parser = subparsers.add_parser('run', help='Run a command with lifecycle monitoring')
    run_parser.add_argument(
        'cmd',
        nargs=argparse.REMAINDER,
        help='The command to execute (use -- to separate from slm args)'
    )

    # Query subcommand
    query_parser = subparsers.add_parser('query', help='Query job information from database')
    query_parser.add_argument('job_id', nargs='?', help='Job ID to query (default: current job)')
    query_parser.add_argument(
        '--events',
        action='store_true',
        help='Show job events'
    )

    args = parser.parse_args()

    # Initialize SDK
    sdk = SlmSDK(db_enabled=not args.no_db)

    if args.command == 'submit':
        # Submit with notification
        if not os.path.exists(args.script):
            print(f"[SLM] Error: Script not found: {args.script}", file=sys.stderr)
            sys.exit(1)

        script_path = os.path.abspath(args.script)
        sbatch_cmd = ['sbatch']
        if args.sbatch_args:
            sbatch_cmd.extend(args.sbatch_args.split())
        sbatch_cmd.append(args.script)

        print(f"[SLM] Submitting job: {args.script}")

        # Run sbatch and capture output to get the real job_id
        result = subprocess.run(sbatch_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[SLM] sbatch failed: {result.stderr}", file=sys.stderr)
            sys.exit(result.returncode)

        # Parse sbatch output to extract real job_id
        # Output format: "Submitted batch job 12345"
        match = re.search(r'Submitted batch job (\d+)', result.stdout)
        if not match:
            print(f"[SLM] Failed to parse sbatch output: {result.stdout}", file=sys.stderr)
            sys.exit(1)

        real_job_id = match.group(1)
        db_job_id = f"slurm-{real_job_id}"

        # Update sdk's job_id to the real one
        sdk.job_id = db_job_id

        # Register job in database with real job_id
        sdk.register_job(script_path=script_path, submission_source='slm_submit')
        sdk._update_job_status("SUBMITTED", script_path=script_path)
        sdk.log_status("SUBMITTED", f"Script: {args.script}, Job ID: {real_job_id}")

        print(f"[SLM] Job submitted successfully: {real_job_id}")
        sys.exit(0)

    elif args.command == 'run':
        # Handle command execution
        if not args.cmd:
            print("[SLM] Error: No command specified", file=sys.stderr)
            print("Usage: slm run -- <your command>", file=sys.stderr)
            sys.exit(1)

        # Remove '--' if present
        actual_cmd = args.cmd[1:] if args.cmd and args.cmd[0] == '--' else args.cmd

        if not actual_cmd:
            print("[SLM] Error: Empty command", file=sys.stderr)
            sys.exit(1)

        sdk.monitor_run(actual_cmd)

    elif args.command == 'query':
        # Query job information
        if not sdk.db:
            print("[SLM] Error: Database not available", file=sys.stderr)
            sys.exit(1)

        job_id = args.job_id or os.getenv('SLURM_JOB_ID', 'N/A')

        if args.events:
            # Show events
            events = sdk.db.get_job_events(job_id)
            if events:
                print(f"\nEvents for job {job_id}:")
                print("-" * 80)
                for event in events:
                    print(f"  {event['created_at']} | {event['event_type']:15} | {event['event_status']:12} | {event['details']}")
            else:
                print(f"[SLM] No events found for job {job_id}")
        else:
            # Show job info
            job_info = sdk.db.get_job_info(job_id)
            if job_info:
                print(f"\nJob Information for {job_id}:")
                print("-" * 80)
                for key, value in job_info.items():
                    if key not in ['id']:
                        print(f"  {key:20}: {value}")
            else:
                print(f"[SLM] No information found for job {job_id}")

        # Close database connection
        if sdk.db:
            close_database()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
