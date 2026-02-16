#!/usr/bin/env python3
"""
HTTP Client for SLM
Sends job updates to login node's HTTP API service
"""

import os
import sys
import json
from typing import Optional, Dict, Any
import urllib.request
import urllib.error


class SlmHTTPClient:
    """HTTP client for communicating with SLM API service"""

    def __init__(self, api_base_url: str = None):
        """
        Initialize HTTP client

        Args:
            api_base_url: Base URL of the API service (default: from env or http://10.11.100.251:8000)
        """
        if api_base_url is None:
            api_base_url = os.getenv("SLM_API_URL", "http://10.11.100.251:9008")

        self.api_base_url = api_base_url.rstrip('/')
        self.enabled = True

        # Test connection on init
        try:
            response = self._request("GET", "/", timeout=2)
            if response and response.get("status") == "running":
                print(f"[SLM.HTTP] Connected to API service at {self.api_base_url}", file=sys.stderr)
            else:
                print(f"[SLM.HTTP] Warning: API service returned unexpected response", file=sys.stderr)
        except Exception as e:
            print(f"[SLM.HTTP] Failed to connect to API service: {e}", file=sys.stderr)
            print(f"[SLM.HTTP] HTTP client disabled", file=sys.stderr)
            self.enabled = False

    def _request(self, method: str, endpoint: str, data: Dict = None, timeout: int = 5) -> Optional[Dict]:
        """
        Send HTTP request

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: Request payload (for POST)
            timeout: Request timeout in seconds

        Returns:
            Response JSON dict, or None if failed
        """
        url = f"{self.api_base_url}{endpoint}"

        try:
            if method == "GET":
                req = urllib.request.Request(url, method='GET')
            else:  # POST
                json_data = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(url, data=json_data, method='POST')
                req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return response_data

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            print(f"[SLM.HTTP] HTTP Error {e.code}: {error_body}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"[SLM.HTTP] Connection Error: {e.reason}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[SLM.HTTP] Request failed: {e}", file=sys.stderr)
            return None

    def update_job_status(self, job_id: str, status: str, **kwargs) -> bool:
        """
        Update job status via HTTP API

        Args:
            job_id: Job ID
            status: New status
            **kwargs: Additional fields (exit_code, command, etc.)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        payload = {
            "job_id": job_id,
            "status": status,
            **kwargs
        }

        response = self._request("POST", "/api/job/status", data=payload)

        if response and response.get("success"):
            print(f"[SLM.HTTP] ✅ Updated job {job_id} to {status} via API", file=sys.stderr)
            return True
        else:
            print(f"[SLM.HTTP] ❌ Failed to update job {job_id} to {status}", file=sys.stderr)
            if response:
                print(f"[SLM.HTTP]    Response: {response.get('message', 'Unknown error')}", file=sys.stderr)
            return False

    def register_job(self, job_id: str, job_name: str, submission_source: str = None, **kwargs) -> Optional[int]:
        """
        Register a new job via HTTP API

        Args:
            job_id: Job ID
            job_name: Job name
            submission_source: Submission source (slm_submit, direct_sbatch, local_test)
            **kwargs: Additional fields

        Returns:
            Record ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        payload = {
            "job_id": job_id,
            "job_name": job_name,
            **kwargs
        }

        if submission_source:
            payload["submission_source"] = submission_source

        response = self._request("POST", "/api/job/register", data=payload)

        if response and response.get("success"):
            record_id = response.get("record_id")
            print(f"[SLM.HTTP] ✅ Registered job {job_id} (source: {submission_source}) via API", file=sys.stderr)
            return record_id
        else:
            print(f"[SLM.HTTP] ❌ Failed to register job {job_id}", file=sys.stderr)
            if response:
                print(f"[SLM.HTTP]    Response: {response.get('message', 'Unknown error')}", file=sys.stderr)
            return None

    def log_event(self, job_id: str, event_type: str, event_status: str,
                  details: str = "", metadata: Dict = None) -> Optional[int]:
        """
        Log a job event via HTTP API

        Args:
            job_id: Job ID
            event_type: Event type
            event_status: Event status
            details: Event details
            metadata: Event metadata

        Returns:
            Event ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        payload = {
            "job_id": job_id,
            "event_type": event_type,
            "event_status": event_status,
            "details": details
        }

        if metadata:
            payload["metadata"] = metadata

        response = self._request("POST", "/api/job/event", data=payload)

        if response and response.get("success"):
            event_id = response.get("event_id")
            print(f"[SLM.HTTP] ✅ Logged event {event_status} for job {job_id} via API", file=sys.stderr)
            return event_id
        else:
            print(f"[SLM.HTTP] ⚠️  Failed to log event for job {job_id}", file=sys.stderr)
            if response:
                print(f"[SLM.HTTP]    Response: {response.get('message', 'Unknown error')}", file=sys.stderr)
            return None


# Singleton instance
_http_client: Optional[SlmHTTPClient] = None


def get_http_client() -> Optional[SlmHTTPClient]:
    """Get or create HTTP client singleton instance"""
    global _http_client

    if _http_client is None:
        try:
            _http_client = SlmHTTPClient()
        except Exception as e:
            print(f"[SLM.HTTP] Failed to initialize HTTP client: {e}", file=sys.stderr)
            _http_client = SlmHTTPClient.__new__(SlmHTTPClient)
            _http_client.enabled = False

    return _http_client if _http_client.enabled else None
