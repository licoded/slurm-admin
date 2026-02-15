"""Slurm Lifecycle Monitor CLI"""

import argparse
import subprocess
import sys

from .sdk import SlmSDK


def cmd_submit(args) -> None:
    """Handle 'submit' subcommand: notify and call sbatch."""
    sdk = SlmSDK(webhook=args.webhook)
    sdk.send_webhook("SUBMITTED", f"Script: {args.script}")

    # Execute real sbatch
    result = subprocess.run(["sbatch"] + args.sbatch_args + [args.script])
    sys.exit(result.returncode)


def cmd_run(args) -> None:
    """Handle 'run' subcommand: wrap command with monitoring."""
    sdk = SlmSDK(webhook=args.webhook)

    # Remove leading '--' if present
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        print("[SLM] Error: No command specified", file=sys.stderr)
        sys.exit(1)

    exit_code = sdk.monitor_run(cmd)
    sys.exit(exit_code)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="slm",
        description="Slurm Lifecycle Monitor - Monitor and notify Slurm job status",
    )
    parser.add_argument(
        "--webhook", "-w",
        help="Webhook URL (overrides SLM_WEBHOOK env var)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit subcommand
    submit_parser = subparsers.add_parser(
        "submit",
        help="Submit a job with notification",
    )
    submit_parser.add_argument("script", help="Script file to submit")
    submit_parser.add_argument(
        "sbatch_args",
        nargs="*",
        help="Additional arguments passed to sbatch",
    )
    submit_parser.set_defaults(func=cmd_submit)

    # run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run a command with lifecycle monitoring",
    )
    run_parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Command to execute (use -- to separate from slm args)",
    )
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
