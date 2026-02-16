#!/usr/bin/env python3
"""
SLM HTTP API Service
Runs on login node to receive job updates from compute nodes via HTTP
"""

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

try:
    from .database import get_database
except ImportError:
    from database import get_database

app = FastAPI(title="SLM Job API", version="1.0.0")

# Get database instance
db = get_database()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "SLM Job API",
        "status": "running",
        "database": "connected" if db and db.enabled else "disabled"
    }


@app.post("/api/job/status")
async def update_job_status(request: Request):
    """
    Update job status

    Expected JSON payload:
    {
        "job_id": "slurm-12345",
        "status": "RUNNING",
        "exit_code": 0,
        "command": "echo test",
        ... (other optional fields)
    }
    """
    try:
        data = await request.json()

        if not data.get("job_id") or not data.get("status"):
            raise HTTPException(status_code=400, detail="Missing required fields: job_id, status")

        job_id = data["job_id"]
        status = data["status"]

        # Extract optional fields
        kwargs = {}
        for key in ["exit_code", "command", "script_path", "nodes", "cpus", "gpus", "memory", "partition_name"]:
            if key in data and data[key] is not None:
                kwargs[key] = data[key]

        # Update database
        success = db.update_job_status(job_id, status, **kwargs)

        if success:
            print(f"[API] ✅ Updated job {job_id} to {status}", flush=True)
            return {
                "success": True,
                "job_id": job_id,
                "status": status,
                "message": "Job status updated successfully"
            }
        else:
            print(f"[API] ⚠️  Job {job_id} not found for update", flush=True)
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "job_id": job_id,
                    "message": "Job not found"
                }
            )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"[API] ❌ Error updating job status: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/job/register")
async def register_job(request: Request):
    """
    Register a new job

    Expected JSON payload:
    {
        "job_id": "slurm-12345",
        "job_name": "MyJob",
        "submission_source": "slm_submit",
        "command": "echo test",
        ... (other optional fields)
    }
    """
    try:
        data = await request.json()

        if not data.get("job_id") or not data.get("job_name"):
            raise HTTPException(status_code=400, detail="Missing required fields: job_id, job_name")

        job_id = data["job_id"]
        job_name = data["job_name"]

        # Extract optional fields
        kwargs = {}
        submission_source = data.get("submission_source")
        for key in ["command", "script_path", "nodes", "cpus", "gpus", "memory", "partition_name"]:
            if key in data and data[key] is not None:
                kwargs[key] = data[key]

        # Register job in database
        record_id = db.register_job(job_id, job_name, submission_source=submission_source, **kwargs)

        if record_id:
            print(f"[API] ✅ Registered job {job_id} (source: {submission_source})", flush=True)
            return {
                "success": True,
                "job_id": job_id,
                "record_id": record_id,
                "message": "Job registered successfully"
            }
        else:
            print(f"[API] ❌ Failed to register job {job_id}", flush=True)
            raise HTTPException(status_code=500, detail="Failed to register job")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"[API] ❌ Error registering job: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/job/event")
async def log_event(request: Request):
    """
    Log a job event

    Expected JSON payload:
    {
        "job_id": "slurm-12345",
        "event_type": "lifecycle",
        "event_status": "RUNNING",
        "details": "Job started",
        "metadata": {...}
    }
    """
    try:
        data = await request.json()

        if not data.get("job_id") or not data.get("event_type") or not data.get("event_status"):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: job_id, event_type, event_status"
            )

        job_id = data["job_id"]
        event_type = data["event_type"]
        event_status = data["event_status"]
        details = data.get("details", "")
        metadata = data.get("metadata")

        # Log event to database
        event_id = db.log_event(job_id, event_type, event_status, details, metadata)

        if event_id:
            print(f"[API] ✅ Logged event {event_status} for job {job_id}", flush=True)
            return {
                "success": True,
                "job_id": job_id,
                "event_id": event_id,
                "message": "Event logged successfully"
            }
        else:
            print(f"[API] ⚠️  Database disabled, event not logged for job {job_id}", flush=True)
            return {
                "success": False,
                "job_id": job_id,
                "message": "Database disabled"
            }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"[API] ❌ Error logging event: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Start the API server"""
    import argparse

    parser = argparse.ArgumentParser(description="SLM HTTP API Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    print(f"[API] Starting SLM HTTP API service on {args.host}:{args.port}", flush=True)
    print(f"[API] Database: {'enabled' if db and db.enabled else 'disabled'}", flush=True)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
