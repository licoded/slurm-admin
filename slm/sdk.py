"""Slurm Lifecycle Monitor SDK - Core functionality"""

import os
import sys
import signal
import subprocess
from datetime import datetime
from typing import Optional

import requests


class SlmSDK:
    """Slurm Lifecycle Monitor SDK for job tracking and notifications."""

    def __init__(self, webhook: Optional[str] = None):
        self.webhook = webhook or os.getenv("SLM_WEBHOOK", "")
        self.job_id = os.getenv("SLURM_JOB_ID", "N/A")
        self.job_name = os.getenv("SLURM_JOB_NAME", "LocalTask")

    def send_webhook(self, status: str, details: str = "") -> bool:
        """Send notification to webhook endpoint."""
        if not self.webhook:
            print(f"[SLM] No webhook configured, skipping notification: {status}", file=sys.stderr)
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"[Slurm {status}]\n"
                        f"JobID: {self.job_id}\n"
                        f"Name: {self.job_name}\n"
                        f"Time: {now}\n"
                        f"Details: {details}"
            }
        }

        try:
            resp = requests.post(self.webhook, json=payload, timeout=5)
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"[SLM] Webhook failed: {e}", file=sys.stderr)
            return False

    def monitor_run(self, cmd_args: list) -> int:
        """
        Wrap and execute a command with signal monitoring.

        Captures SIGTSTP (suspend), SIGCONT (resume), SIGTERM (terminate)
        and sends notifications accordingly.
        """
        self.send_webhook("RUNNING", f"Command: {' '.join(cmd_args)}")

        # Signal handler
        def handle_signal(signum: int, frame) -> None:
            sig_map = {
                signal.SIGTSTP: "PAUSED",
                signal.SIGCONT: "RESUMED",
                signal.SIGTERM: "TERMINATING",
            }
            status = sig_map.get(signum, f"SIGNAL_{signum}")
            self.send_webhook(status)

        # Register signal handlers
        signal.signal(signal.SIGTSTP, handle_signal)  # scontrol suspend
        signal.signal(signal.SIGCONT, handle_signal)  # scontrol resume
        signal.signal(signal.SIGTERM, handle_signal)  # scancel/timeout

        # Execute subprocess
        process = subprocess.Popen(cmd_args)
        exit_code = process.wait()

        # Final notification
        final_status = "COMPLETED" if exit_code == 0 else f"FAILED (Code: {exit_code})"
        self.send_webhook(final_status)

        return exit_code
