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
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None
    print("[SLM] Warning: 'requests' module not found. Webhooks will be disabled.", file=sys.stderr)

try:
    from database import get_database, close_database, DatabaseConfig
except ImportError:
    print("[SLM] Warning: 'database' module not found. Database logging will be disabled.", file=sys.stderr)
    get_database = None
    close_database = None
    DatabaseConfig = None


class SlmSDK:
    """Slurm Lifecycle Monitor SDK"""

    def __init__(self, webhook: Optional[str] = None, db_enabled: bool = True):
        # Priority: CLI argument > Environment variable > Default
        self.webhook = webhook or os.getenv("SLM_WEBHOOK", "")
        self.job_id = os.getenv('SLURM_JOB_ID', 'N/A')
        self.job_name = os.getenv('SLURM_JOB_NAME', 'LocalTask')
        self.job_nodes = os.getenv('SLURM_JOB_NODELIST', 'N/A')
        self.job_cpus = os.getenv('SLURM_CPUS_PER_TASK', 'N/A')
        self.job_gpus = os.getenv('SLURM_JOB_GRES', 'N/A')
        self.job_mem = os.getenv('SLURM_MEM_PER_NODE', 'N/A')
        self.job_partition = os.getenv('SLURM_JOB_PARTITION', 'N/A')

        # Initialize database
        self.db = get_database() if (db_enabled and get_database) else None
        if self.db:
            print(f"[SLM.DB] Database logging enabled", file=sys.stderr)

    def _log_event(self, event_type: str, event_status: str, details: str = "", metadata: Optional[Dict] = None):
        """Log event to database"""
        if self.db:
            self.db.log_event(self.job_id, event_type, event_status, details, metadata)

    def _update_job_status(self, status: str, **kwargs):
        """Update job status in database"""
        if self.db:
            self.db.update_job_status(self.job_id, status, **kwargs)

    def send_webhook(self, status: str, details: str = ""):
        """Send webhook notification and log to database"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Log to database
        self._log_event("lifecycle", status, details, {"timestamp": now})

        # Send webhook if configured
        if not self.webhook:
            print(f"[SLM] No webhook configured. Status: {status}", file=sys.stderr)
            return

        if not requests:
            print(f"[SLM] Requests module not available. Status: {status}", file=sys.stderr)
            return

        # Build emoji map for different statuses
        emoji_map = {
            "SUBMITTED": "📤",
            "RUNNING": "▶️",
            "PAUSED": "⏸️",
            "RESUMED": "▶️",
            "TERMINATING": "⏹️",
            "COMPLETED": "✅",
            "FAILED": "❌"
        }

        emoji = emoji_map.get(status, "📊")

        payload = {
            "msg_type": "text",
            "content": {
                "text": (
                    f"{emoji} [Slurm {status}]\n"
                    f"🆔 JobID: {self.job_id}\n"
                    f"📝 Name: {self.job_name}\n"
                    f"🖥️ Nodes: {self.job_nodes}\n"
                    f"⚙️ CPUs: {self.job_cpus}\n"
                    f"🎮 GPUs: {self.job_gpus}\n"
                    f"💾 Memory: {self.job_mem}\n"
                    f"🔀 Partition: {self.job_partition}\n"
                    f"⏰ Time: {now}\n"
                    f"ℹ️ Details: {details}"
                )
            }
        }

        try:
            response = requests.post(self.webhook, json=payload, timeout=5)
            if response.status_code != 200:
                print(f"[SLM] Webhook returned status {response.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"[SLM] Webhook failed: {e}", file=sys.stderr)

    def register_job(self, script_path: str = None, command: str = None):
        """Register job in database"""
        if self.db:
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
            self.db.register_job(self.job_id, self.job_name, **job_data)

    def monitor_run(self, cmd_args: List[str]):
        """Core monitoring logic: wrap and execute the actual command"""
        if not cmd_args:
            print("[SLM] Error: No command provided to run", file=sys.stderr)
            sys.exit(1)

        cmd_str = ' '.join(cmd_args)
        print(f"[SLM] Starting command: {cmd_str}")

        # Register job and update status to RUNNING
        self.register_job(command=cmd_str)
        self._update_job_status("RUNNING", command=cmd_str)
        self.send_webhook("RUNNING", f"Command: {cmd_str}")

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

            # Only send webhook for first occurrence of each signal type
            if signal_received["signal"] != status:
                signal_received["signal"] = status
                self._update_job_status(status)
                self.send_webhook(status, f"Received signal: {signal_name}")

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
            self.send_webhook(final_status, details)

            # Close database connection before exit
            if self.db:
                close_database()

            sys.exit(exit_code)

        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            print(f"[SLM] {error_msg}", file=sys.stderr)

            self._update_job_status("FAILED")
            self.send_webhook("FAILED", error_msg)

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
  slm submit job_script.sh

  # Run a command with monitoring
  slm run -- python train.py --epochs 100

  # Run with environment variable for webhook
  export SLM_WEBHOOK="https://your-webhook-url.com"
  slm run -- bash my_script.sh

  # Disable database logging
  slm --no-db run -- python script.py
        """
    )

    parser.add_argument(
        '--webhook',
        help='Webhook URL (overrides SLM_WEBHOOK env var)'
    )

    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Disable database logging'
    )

    parser.add_argument(
        '--db-host',
        help='Database host (overrides SLM_DB_HOST env var)'
    )

    parser.add_argument(
        '--db-port',
        type=int,
        help='Database port (overrides SLM_DB_PORT env var)'
    )

    parser.add_argument(
        '--db-user',
        help='Database user (overrides SLM_DB_USER env var)'
    )

    parser.add_argument(
        '--db-password',
        help='Database password (overrides SLM_DB_PASSWORD env var)'
    )

    parser.add_argument(
        '--db-name',
        help='Database name (overrides SLM_DB_NAME env var)'
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

    # Query subcommand - new!
    query_parser = subparsers.add_parser('query', help='Query job information from database')
    query_parser.add_argument('job_id', nargs='?', help='Job ID to query (default: current job)')
    query_parser.add_argument(
        '--events',
        action='store_true',
        help='Show job events'
    )

    args = parser.parse_args()

    # Set database environment variables from CLI args if provided
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

    # Initialize SDK
    sdk = SlmSDK(webhook=args.webhook, db_enabled=not args.no_db)

    if args.command == 'submit':
        # Submit with notification
        if not os.path.exists(args.script):
            print(f"[SLM] Error: Script not found: {args.script}", file=sys.stderr)
            sys.exit(1)

        # Register job in database
        script_path = os.path.abspath(args.script)
        sdk.register_job(script_path=script_path)
        sdk._update_job_status("SUBMITTED", script_path=script_path)
        sdk.send_webhook("SUBMITTED", f"Script: {args.script}")

        sbatch_cmd = ['sbatch']
        if args.sbatch_args:
            sbatch_cmd.extend(args.sbatch_args.split())
        sbatch_cmd.append(args.script)

        print(f"[SLM] Submitting job: {args.script}")
        result = subprocess.run(sbatch_cmd)

        if result.returncode != 0:
            sdk._update_job_status("FAILED")
            sdk.send_webhook("FAILED", f"sbatch failed with code {result.returncode}")

        sys.exit(result.returncode)

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
