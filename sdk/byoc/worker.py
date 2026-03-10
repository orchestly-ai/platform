"""
BYOC Worker - Main Worker Implementation

The Worker class is the main entry point for BYOC deployments.
It polls the Agent Orchestration platform for jobs and executes them
on customer's infrastructure.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from uuid import uuid4

import httpx

from .models import (
    Job,
    JobResult,
    JobStatus,
    WorkerConfig,
    WorkerStatus,
    LLMProviderConfig,
)
from .executor import WorkflowExecutor

logger = logging.getLogger(__name__)


class Worker:
    """
    BYOC Worker for executing workflows on customer infrastructure.

    This worker:
    1. Registers with the Agent Orchestration platform
    2. Polls for pending jobs
    3. Executes jobs using configured LLM providers (BYOK)
    4. Reports results back to the platform

    Usage:
        worker = Worker(
            api_url="https://api.agent-orchestration.com",
            api_key="your-api-key",
            organization_id="your-org",
            llm_providers=[
                LLMProviderConfig(provider="openai", api_key="sk-..."),
            ],
        )
        worker.start()
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        organization_id: str,
        worker_id: Optional[str] = None,
        max_concurrent_jobs: int = 1,
        poll_interval_seconds: float = 5.0,
        heartbeat_interval_seconds: float = 30.0,
        job_timeout_seconds: int = 3600,
        llm_providers: Optional[List[LLMProviderConfig]] = None,
        capabilities: Optional[List[str]] = None,
        log_level: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.config = WorkerConfig(
            api_url=api_url.rstrip("/"),
            api_key=api_key,
            organization_id=organization_id,
            worker_id=worker_id or f"worker-{uuid4().hex[:8]}",
            max_concurrent_jobs=max_concurrent_jobs,
            poll_interval_seconds=poll_interval_seconds,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            job_timeout_seconds=job_timeout_seconds,
            llm_providers=llm_providers or [],
            capabilities=capabilities,
            log_level=log_level,
            metadata=metadata,
        )

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

        # Worker state
        self._running = False
        self._current_jobs: Dict[str, Job] = {}
        self._status = WorkerStatus(
            worker_id=self.config.worker_id,
            organization_id=organization_id,
            status="offline",
            started_at=None,
        )

        # Executor
        self._executor = WorkflowExecutor(self.config.llm_providers)

        # Callbacks
        self._on_job_start: Optional[Callable[[Job], None]] = None
        self._on_job_complete: Optional[Callable[[Job, JobResult], None]] = None
        self._on_job_error: Optional[Callable[[Job, Exception], None]] = None

    async def _init_client(self):
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "X-Organization-Id": self.config.organization_id,
                    "X-Worker-Id": self.config.worker_id,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

    async def _close_client(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def register(self) -> bool:
        """Register this worker with the platform."""
        await self._init_client()

        try:
            response = await self._client.post(
                "/api/byoc/workers/register",
                json={
                    "worker_id": self.config.worker_id,
                    "organization_id": self.config.organization_id,
                    "max_concurrent_jobs": self.config.max_concurrent_jobs,
                    "capabilities": self.config.capabilities,
                    "metadata": self.config.metadata,
                },
            )

            if response.status_code in [200, 201]:
                logger.info(f"Worker registered: {self.config.worker_id}")
                self._status.status = "idle"
                self._status.started_at = datetime.utcnow()
                return True
            else:
                logger.error(f"Failed to register worker: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error registering worker: {e}")
            return False

    async def unregister(self):
        """Unregister this worker from the platform."""
        if not self._client:
            return

        try:
            await self._client.post(
                f"/api/byoc/workers/{self.config.worker_id}/unregister",
            )
            logger.info(f"Worker unregistered: {self.config.worker_id}")
        except Exception as e:
            logger.error(f"Error unregistering worker: {e}")

    async def heartbeat(self):
        """Send heartbeat to the platform."""
        if not self._client:
            return

        try:
            await self._client.post(
                f"/api/byoc/workers/{self.config.worker_id}/heartbeat",
                json={
                    "status": self._status.status,
                    "current_job_id": self._status.current_job_id,
                    "jobs_completed": self._status.jobs_completed,
                    "jobs_failed": self._status.jobs_failed,
                },
            )
            self._status.last_heartbeat = datetime.utcnow()
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")

    async def poll_job(self) -> Optional[Job]:
        """Poll for a pending job."""
        if not self._client:
            return None

        try:
            response = await self._client.get(
                "/api/byoc/jobs/next",
                params={
                    "worker_id": self.config.worker_id,
                    "capabilities": ",".join(self.config.capabilities or []),
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data:
                    return Job.from_dict(data)
            elif response.status_code == 204:
                # No jobs available
                return None
            else:
                logger.warning(f"Error polling for jobs: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error polling for jobs: {e}")
            return None

    async def claim_job(self, job_id: str) -> bool:
        """Claim a job for execution."""
        if not self._client:
            return False

        try:
            response = await self._client.post(
                f"/api/byoc/jobs/{job_id}/claim",
                json={"worker_id": self.config.worker_id},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error claiming job: {e}")
            return False

    async def submit_result(self, result: JobResult) -> bool:
        """Submit job result to the platform."""
        if not self._client:
            return False

        try:
            response = await self._client.post(
                f"/api/byoc/jobs/{result.job_id}/result",
                json=result.to_dict(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error submitting result: {e}")
            return False

    async def execute_job(self, job: Job) -> JobResult:
        """Execute a job."""
        started_at = datetime.utcnow()
        self._status.current_job_id = job.job_id
        self._status.status = "busy"

        if self._on_job_start:
            self._on_job_start(job)

        try:
            # Execute the workflow
            output, step_results = await self._executor.execute(
                workflow_definition=job.workflow_definition,
                input_data=job.input_data,
                context=job.context,
                timeout_seconds=job.timeout_seconds,
            )

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            result = JobResult(
                job_id=job.job_id,
                status=JobStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                step_results=step_results,
                tokens_used=self._executor.total_tokens,
                cost=self._executor.total_cost,
            )

            self._status.jobs_completed += 1
            self._status.total_duration_seconds += duration

            if self._on_job_complete:
                self._on_job_complete(job, result)

            return result

        except asyncio.TimeoutError:
            logger.error(f"Job {job.job_id} timed out")
            return JobResult(
                job_id=job.job_id,
                status=JobStatus.TIMEOUT,
                error="Job execution timed out",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            import traceback
            logger.error(f"Job {job.job_id} failed: {e}")

            if self._on_job_error:
                self._on_job_error(job, e)

            self._status.jobs_failed += 1

            return JobResult(
                job_id=job.job_id,
                status=JobStatus.FAILED,
                error=str(e),
                error_traceback=traceback.format_exc(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        finally:
            self._status.current_job_id = None
            self._status.status = "idle"

    async def _heartbeat_loop(self):
        """Background task to send heartbeats."""
        while self._running:
            await self.heartbeat()
            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    async def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                # Check if we can accept more jobs
                if len(self._current_jobs) >= self.config.max_concurrent_jobs:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                # Poll for a job
                job = await self.poll_job()

                if job:
                    # Claim the job
                    if await self.claim_job(job.job_id):
                        logger.info(f"Executing job: {job.job_id}")
                        self._current_jobs[job.job_id] = job

                        # Execute in background
                        asyncio.create_task(self._execute_and_report(job))
                    else:
                        logger.warning(f"Failed to claim job: {job.job_id}")

                await asyncio.sleep(self.config.poll_interval_seconds)

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                await asyncio.sleep(self.config.poll_interval_seconds)

    async def _execute_and_report(self, job: Job):
        """Execute a job and report the result."""
        try:
            result = await self.execute_job(job)
            await self.submit_result(result)
        finally:
            self._current_jobs.pop(job.job_id, None)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    async def run(self):
        """Run the worker (async)."""
        logger.info(f"Starting BYOC Worker: {self.config.worker_id}")

        # Register
        if not await self.register():
            logger.error("Failed to register worker, exiting")
            return

        self._running = True

        # Start background tasks
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        poll_task = asyncio.create_task(self._poll_loop())

        try:
            # Wait until stopped
            while self._running:
                await asyncio.sleep(1)
        finally:
            # Cleanup
            self._running = False
            heartbeat_task.cancel()
            poll_task.cancel()

            # Wait for current jobs to complete (with timeout)
            if self._current_jobs:
                logger.info(f"Waiting for {len(self._current_jobs)} jobs to complete...")
                await asyncio.sleep(5)  # Give jobs time to complete

            await self.unregister()
            await self._close_client()

        logger.info("Worker stopped")

    def start(self):
        """Start the worker (blocking)."""
        self._setup_signal_handlers()
        asyncio.run(self.run())

    def on_job_start(self, callback: Callable[[Job], None]):
        """Set callback for job start."""
        self._on_job_start = callback

    def on_job_complete(self, callback: Callable[[Job, JobResult], None]):
        """Set callback for job completion."""
        self._on_job_complete = callback

    def on_job_error(self, callback: Callable[[Job, Exception], None]):
        """Set callback for job errors."""
        self._on_job_error = callback
