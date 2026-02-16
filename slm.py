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
from typing import Optional, List

try:
    import requests
except ImportError:
    requests = None
    print("[SLM] Warning: 'requests' module not found. Webhooks will be disabled.", file=sys.stderr)


class SlmSDK:
    """Slurm Lifecycle Monitor SDK"""

    def __init__(self, webhook: Optional[str] = None):
        # Priority: CLI argument > Environment variable > Default
        self.webhook = webhook or os.getenv("SLM_WEBHOOK", "")
        self.job_id = os.getenv('SLURM_JOB_ID', 'N/A')
        self.job_name = os.getenv('SLURM_JOB_NAME', 'LocalTask')
        self.job_nodes = os.getenv('SLURM_JOB_NODELIST', 'N/A')
        self.job_cpus = os.getenv('SLURM_CPUS_PER_TASK', 'N/A')

    def send_webhook(self, status: str, details: str = ""):
        """Send webhook notification"""
        if not self.webhook:
            print(f"[SLM] No webhook configured. Status: {status}", file=sys.stderr)
            return

        if not requests:
            print(f"[SLM] Requests module not available. Status: {status}", file=sys.stderr)
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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

    def monitor_run(self, cmd_args: List[str]):
        """Core monitoring logic: wrap and execute the actual command"""
        if not cmd_args:
            print("[SLM] Error: No command provided to run", file=sys.stderr)
            sys.exit(1)

        cmd_str = ' '.join(cmd_args)
        print(f"[SLM] Starting command: {cmd_str}")
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
                self.send_webhook(status, f"Received signal: {signal_name}")

                if status == "TERMINATING":
                    print(f"[SLM] Received {signal_name}, terminating...", file=sys.stderr)
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

            self.send_webhook(final_status, details)
            sys.exit(exit_code)

        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            print(f"[SLM] {error_msg}", file=sys.stderr)
            self.send_webhook("FAILED", error_msg)
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
        """
    )

    parser.add_argument(
        '--webhook',
        help='Webhook URL (overrides SLM_WEBHOOK env var)'
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

    args = parser.parse_args()

    # Initialize SDK
    sdk = SlmSDK(webhook=args.webhook)

    if args.command == 'submit':
        # Submit with notification
        if not os.path.exists(args.script):
            print(f"[SLM] Error: Script not found: {args.script}", file=sys.stderr)
            sys.exit(1)

        sbatch_cmd = ['sbatch']
        if args.sbatch_args:
            sbatch_cmd.extend(args.sbatch_args.split())
        sbatch_cmd.append(args.script)

        sdk.send_webhook("SUBMITTED", f"Script: {args.script}")

        print(f"[SLM] Submitting job: {args.script}")
        result = subprocess.run(sbatch_cmd)

        if result.returncode != 0:
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

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
