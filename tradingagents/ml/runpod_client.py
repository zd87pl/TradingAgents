"""
RunPod Serverless API Client

This module provides a client for interacting with RunPod Serverless endpoints.
It handles job submission, polling for results, error handling, and retries.

Usage:
    from tradingagents.ml.runpod_client import RunPodClient

    client = RunPodClient(
        endpoint_id="your-endpoint-id",
        api_key="your-api-key"
    )

    result = client.run(
        input_data={"action": "predict", "features": [...]}
    )
"""

import requests
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class RunPodClientError(Exception):
    """Base exception for RunPod client errors"""
    pass


class RunPodTimeoutError(RunPodClientError):
    """Raised when a job times out"""
    pass


class RunPodJobError(RunPodClientError):
    """Raised when a job fails"""
    pass


class RunPodClient:
    """
    Client for RunPod Serverless API.

    Provides async job submission with polling and caching support.
    """

    def __init__(
        self,
        endpoint_id: str,
        api_key: str,
        base_url: str = "https://api.runpod.ai/v2",
        default_timeout: int = 300,  # 5 minutes
        poll_interval: float = 1.0,  # Poll every 1 second
        enable_cache: bool = True,
        cache_ttl: int = 900,  # 15 minutes
    ):
        """
        Initialize RunPod client.

        Args:
            endpoint_id: Your RunPod endpoint ID
            api_key: Your RunPod API key
            base_url: RunPod API base URL
            default_timeout: Default timeout in seconds
            poll_interval: How often to poll for results (seconds)
            enable_cache: Whether to enable result caching
            cache_ttl: Cache time-to-live in seconds
        """
        self.endpoint_id = endpoint_id
        self.api_key = api_key
        self.base_url = base_url
        self.default_timeout = default_timeout
        self.poll_interval = poll_interval
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl

        # Simple in-memory cache
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Construct URLs
        self.run_url = f"{base_url}/{endpoint_id}/run"
        self.status_url = f"{base_url}/{endpoint_id}/status"

        # Headers for requests
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _get_cache_key(self, input_data: Dict[str, Any]) -> str:
        """Generate cache key from input data"""
        # Simple hash of JSON representation
        return str(hash(json.dumps(input_data, sort_keys=True)))

    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if result is in cache and not expired"""
        if not self.enable_cache:
            return None

        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            expiry_time = cache_entry["cached_at"] + timedelta(seconds=self.cache_ttl)

            if datetime.now() < expiry_time:
                print(f"RunPod: Cache hit for key {cache_key[:8]}... (age: {(datetime.now() - cache_entry['cached_at']).seconds}s)")
                return cache_entry["result"]
            else:
                # Expired, remove from cache
                del self._cache[cache_key]

        return None

    def _store_cache(self, cache_key: str, result: Dict[str, Any]):
        """Store result in cache"""
        if not self.enable_cache:
            return

        self._cache[cache_key] = {
            "result": result,
            "cached_at": datetime.now()
        }

    def _clean_cache(self):
        """Remove expired entries from cache"""
        if not self.enable_cache:
            return

        now = datetime.now()
        expired_keys = [
            key for key, value in self._cache.items()
            if now > value["cached_at"] + timedelta(seconds=self.cache_ttl)
        ]

        for key in expired_keys:
            del self._cache[key]

    def submit_job(self, input_data: Dict[str, Any]) -> str:
        """
        Submit a job to RunPod.

        Args:
            input_data: Input dictionary to send to the endpoint

        Returns:
            Job ID

        Raises:
            RunPodClientError: If submission fails
        """
        payload = {"input": input_data}

        try:
            response = requests.post(
                self.run_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if "id" not in result:
                raise RunPodClientError(f"No job ID in response: {result}")

            job_id = result["id"]
            print(f"RunPod: Job submitted successfully (ID: {job_id})")
            return job_id

        except requests.exceptions.RequestException as e:
            raise RunPodClientError(f"Failed to submit job: {e}")

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a running job.

        Args:
            job_id: Job ID to check

        Returns:
            Status response dictionary

        Raises:
            RunPodClientError: If status check fails
        """
        try:
            response = requests.get(
                f"{self.status_url}/{job_id}",
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RunPodClientError(f"Failed to get job status: {e}")

    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Poll for job completion.

        Args:
            job_id: Job ID to wait for
            timeout: Timeout in seconds (uses default if None)
            verbose: Whether to print progress

        Returns:
            Job result output

        Raises:
            RunPodTimeoutError: If job times out
            RunPodJobError: If job fails
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        if verbose:
            print(f"RunPod: Waiting for job {job_id}...")

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout:
                raise RunPodTimeoutError(
                    f"Job {job_id} timed out after {timeout}s"
                )

            # Get status
            status_response = self.get_job_status(job_id)
            status = status_response.get("status")

            if verbose and int(elapsed) % 5 == 0:  # Print every 5 seconds
                print(f"RunPod: Job status: {status} (elapsed: {elapsed:.1f}s)")

            # Check if completed
            if status == "COMPLETED":
                output = status_response.get("output")
                if output is None:
                    raise RunPodJobError(f"Job {job_id} completed but no output")

                if verbose:
                    print(f"RunPod: Job {job_id} completed successfully in {elapsed:.2f}s")

                return output

            # Check if failed
            elif status == "FAILED":
                error = status_response.get("error", "Unknown error")
                raise RunPodJobError(f"Job {job_id} failed: {error}")

            # Still running or in queue
            elif status in ["IN_QUEUE", "IN_PROGRESS"]:
                time.sleep(self.poll_interval)

            else:
                # Unknown status
                raise RunPodJobError(
                    f"Job {job_id} has unknown status: {status}"
                )

    def run(
        self,
        input_data: Dict[str, Any],
        timeout: Optional[int] = None,
        verbose: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Submit a job and wait for completion (blocking call).

        This is the main method to use for synchronous inference.

        Args:
            input_data: Input dictionary for the endpoint
            timeout: Timeout in seconds
            verbose: Whether to print progress
            use_cache: Whether to use cached results

        Returns:
            Job output dictionary

        Raises:
            RunPodClientError: If job fails
            RunPodTimeoutError: If job times out
        """
        # Check cache first
        if use_cache and self.enable_cache:
            cache_key = self._get_cache_key(input_data)
            cached_result = self._check_cache(cache_key)

            if cached_result is not None:
                return cached_result

        # Submit job
        job_id = self.submit_job(input_data)

        # Wait for completion
        result = self.wait_for_completion(job_id, timeout, verbose)

        # Store in cache
        if use_cache and self.enable_cache:
            cache_key = self._get_cache_key(input_data)
            self._store_cache(cache_key, result)

        # Clean expired cache entries periodically
        self._clean_cache()

        return result

    def run_async(self, input_data: Dict[str, Any]) -> str:
        """
        Submit a job without waiting (non-blocking).

        Use this for fire-and-forget or when you want to poll manually.

        Args:
            input_data: Input dictionary for the endpoint

        Returns:
            Job ID (use get_job_status() or wait_for_completion() to retrieve results)
        """
        return self.submit_job(input_data)

    def health_check(self) -> bool:
        """
        Check if the RunPod endpoint is healthy.

        Returns:
            True if endpoint is reachable, False otherwise
        """
        try:
            # Try to submit a minimal health check job
            test_input = {"action": "health_check"}
            response = requests.post(
                self.run_url,
                headers=self.headers,
                json={"input": test_input},
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            print(f"RunPod health check failed: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    # This is for testing purposes
    print("RunPod Client Module")
    print("=" * 50)
    print("\nUsage example:")
    print("""
    from tradingagents.ml.runpod_client import RunPodClient

    # Initialize client
    client = RunPodClient(
        endpoint_id="your-endpoint-id",
        api_key="your-api-key"
    )

    # Run inference (blocking)
    result = client.run({
        "action": "predict",
        "data": {
            "symbol": "AAPL",
            "features": [...]
        }
    })

    print(result)

    # Or run async (non-blocking)
    job_id = client.run_async({...})
    # ... do other work ...
    result = client.wait_for_completion(job_id)
    """)
