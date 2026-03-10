"""
BYOC API Endpoints - Bring Your Own Compute

Endpoints for BYOC workers to:
- Register/unregister with the platform
- Poll for pending jobs
- Claim jobs for execution
- Submit job results
- Send heartbeats

Workers run on customer's infrastructure and use their own LLM keys (BYOK).
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from backend.database.session import AsyncSessionLocal

router = APIRouter(prefix="/api/byoc", tags=["byoc"])


# ==================== In-Memory Storage (Replace with DB in production) ====================

# For MVP, store jobs and workers in memory
# In production, this would use the database
_workers: Dict[str, Dict[str, Any]] = {}
_job_queue: Dict[str, Dict[str, Any]] = {}
_job_results: Dict[str, Dict[str, Any]] = {}


# ==================== Pydantic Models ====================

class WorkerRegistration(BaseModel):
    """Register a BYOC worker"""
    worker_id: str
    organization_id: Optional[str] = None  # Can be provided via header
    max_concurrent_jobs: int = Field(default=1, ge=1, le=100)
    capabilities: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkerHeartbeat(BaseModel):
    """Worker heartbeat"""
    status: str = Field(default="idle", description="idle, busy, offline")
    current_job_id: Optional[str] = None
    jobs_completed: Optional[int] = None
    jobs_failed: Optional[int] = None
    total_duration_seconds: Optional[float] = None


class JobClaim(BaseModel):
    """Claim a job for execution"""
    worker_id: str


class JobSubmission(BaseModel):
    """Submit a job for execution (internal use)"""
    workflow_id: str
    execution_id: str
    organization_id: str
    workflow_definition: Dict[str, Any]
    input_data: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 3600
    max_retries: int = 3
    priority: int = 0
    scheduled_for: Optional[datetime] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class JobResult(BaseModel):
    """Job execution result"""
    job_id: str
    status: str = Field(..., description="completed, failed, timeout, cancelled")
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    step_results: Optional[List[Dict[str, Any]]] = None
    logs: Optional[List[str]] = None


class WorkerResponse(BaseModel):
    """Worker info response"""
    worker_id: str
    organization_id: str
    status: str
    max_concurrent_jobs: int
    capabilities: Optional[List[str]]
    current_job_id: Optional[str]
    jobs_completed: int
    jobs_failed: int
    total_duration_seconds: float = 0
    metadata: Optional[Dict[str, Any]] = None
    registered_at: datetime
    last_heartbeat: Optional[datetime]


class JobResponse(BaseModel):
    """Job info response"""
    job_id: str
    workflow_id: str
    execution_id: str
    organization_id: str
    workflow_definition: Dict[str, Any]
    input_data: Optional[Dict[str, Any]]
    timeout_seconds: int
    max_retries: int
    retry_count: int
    priority: int
    scheduled_for: Optional[datetime]
    status: str
    claimed_by: Optional[str]
    created_at: datetime


# ==================== Helper Functions ====================

def get_org_id(x_organization_id: str = Header(default="default-org")) -> str:
    """Get organization ID from header"""
    return x_organization_id


def get_worker_id(x_worker_id: str = Header(default=None)) -> Optional[str]:
    """Get worker ID from header"""
    return x_worker_id


# ==================== Worker Management Endpoints ====================

@router.post("/workers/register", response_model=WorkerResponse)
async def register_worker(
    registration: WorkerRegistration,
    org_id: str = Depends(get_org_id),
):
    """
    Register a BYOC worker with the platform.

    Workers must register before they can poll for and execute jobs.
    Organization ID can be provided in the body or via X-Organization-Id header.
    """
    worker_id = registration.worker_id
    # Use org_id from body if provided, otherwise from header
    organization_id = registration.organization_id or org_id

    if worker_id in _workers:
        # Update existing worker
        _workers[worker_id].update({
            "status": "idle",
            "max_concurrent_jobs": registration.max_concurrent_jobs,
            "capabilities": registration.capabilities,
            "metadata": registration.metadata,
            "last_heartbeat": datetime.utcnow(),
        })
    else:
        # Create new worker
        _workers[worker_id] = {
            "worker_id": worker_id,
            "organization_id": organization_id,
            "status": "idle",
            "max_concurrent_jobs": registration.max_concurrent_jobs,
            "capabilities": registration.capabilities or [],
            "metadata": registration.metadata,
            "current_job_id": None,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "registered_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow(),
        }

    worker = _workers[worker_id]
    return WorkerResponse(
        worker_id=worker["worker_id"],
        organization_id=worker["organization_id"],
        status=worker["status"],
        max_concurrent_jobs=worker["max_concurrent_jobs"],
        capabilities=worker.get("capabilities"),
        current_job_id=worker.get("current_job_id"),
        jobs_completed=worker.get("jobs_completed", 0),
        jobs_failed=worker.get("jobs_failed", 0),
        total_duration_seconds=worker.get("total_duration_seconds", 0),
        metadata=worker.get("metadata"),
        registered_at=worker["registered_at"],
        last_heartbeat=worker.get("last_heartbeat"),
    )


@router.post("/workers/{worker_id}/unregister")
async def unregister_worker(worker_id: str):
    """Unregister a BYOC worker."""
    if worker_id in _workers:
        _workers[worker_id]["status"] = "offline"
        return {"status": "unregistered", "worker_id": worker_id}
    return {"status": "not_found", "worker_id": worker_id}


@router.delete("/workers/{worker_id}")
async def delete_worker(worker_id: str, org_id: str = Depends(get_org_id)):
    """Delete/remove a BYOC worker."""
    if worker_id not in _workers:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker = _workers[worker_id]
    if worker["organization_id"] != org_id:
        raise HTTPException(status_code=403, detail="Worker belongs to another organization")

    del _workers[worker_id]
    return {"status": "deleted", "worker_id": worker_id}


@router.post("/workers/{worker_id}/heartbeat")
async def worker_heartbeat(
    worker_id: str,
    heartbeat: Optional[WorkerHeartbeat] = None,
):
    """
    Send worker heartbeat.

    Workers should send heartbeats periodically to indicate they're still alive.
    Body is optional - can send empty POST to just update last_heartbeat.
    """
    if worker_id not in _workers:
        raise HTTPException(status_code=404, detail="Worker not registered")

    update_data = {"last_heartbeat": datetime.utcnow()}

    if heartbeat:
        update_data["status"] = heartbeat.status
        if heartbeat.current_job_id is not None:
            update_data["current_job_id"] = heartbeat.current_job_id
        if heartbeat.jobs_completed is not None:
            update_data["jobs_completed"] = heartbeat.jobs_completed
        if heartbeat.jobs_failed is not None:
            update_data["jobs_failed"] = heartbeat.jobs_failed
        if heartbeat.total_duration_seconds is not None:
            update_data["total_duration_seconds"] = heartbeat.total_duration_seconds

    _workers[worker_id].update(update_data)

    return {"status": "ok", "worker_id": worker_id, "last_heartbeat": update_data["last_heartbeat"].isoformat()}


@router.get("/workers", response_model=List[WorkerResponse])
async def list_workers(
    org_id: str = Depends(get_org_id),
    status: Optional[str] = None,
):
    """List all workers for the organization."""
    workers = []
    for w in _workers.values():
        if w["organization_id"] != org_id:
            continue
        if status and w["status"] != status:
            continue
        workers.append(WorkerResponse(
            worker_id=w["worker_id"],
            organization_id=w["organization_id"],
            status=w["status"],
            max_concurrent_jobs=w["max_concurrent_jobs"],
            capabilities=w.get("capabilities"),
            current_job_id=w.get("current_job_id"),
            jobs_completed=w.get("jobs_completed", 0),
            jobs_failed=w.get("jobs_failed", 0),
            total_duration_seconds=w.get("total_duration_seconds", 0),
            metadata=w.get("metadata"),
            registered_at=w["registered_at"],
            last_heartbeat=w.get("last_heartbeat"),
        ))
    return workers


@router.get("/workers/{worker_id}", response_model=WorkerResponse)
async def get_worker(worker_id: str):
    """Get worker details."""
    if worker_id not in _workers:
        raise HTTPException(status_code=404, detail="Worker not found")

    w = _workers[worker_id]
    return WorkerResponse(
        worker_id=w["worker_id"],
        organization_id=w["organization_id"],
        status=w["status"],
        max_concurrent_jobs=w["max_concurrent_jobs"],
        capabilities=w.get("capabilities"),
        current_job_id=w.get("current_job_id"),
        jobs_completed=w.get("jobs_completed", 0),
        jobs_failed=w.get("jobs_failed", 0),
        total_duration_seconds=w.get("total_duration_seconds", 0),
        metadata=w.get("metadata"),
        registered_at=w["registered_at"],
        last_heartbeat=w.get("last_heartbeat"),
    )


# ==================== Job Management Endpoints ====================

@router.post("/jobs", response_model=JobResponse)
async def submit_job(
    job: JobSubmission,
    org_id: str = Depends(get_org_id),
):
    """
    Submit a job for BYOC execution.

    Jobs are queued and picked up by available workers.
    """
    job_id = str(uuid4())

    job_data = {
        "job_id": job_id,
        "workflow_id": job.workflow_id,
        "execution_id": job.execution_id,
        "organization_id": org_id,
        "workflow_definition": job.workflow_definition,
        "input_data": job.input_data,
        "timeout_seconds": job.timeout_seconds,
        "max_retries": job.max_retries,
        "retry_count": 0,
        "priority": job.priority,
        "scheduled_for": job.scheduled_for,
        "context": job.context,
        "metadata": job.metadata,
        "status": "pending",
        "claimed_by": None,
        "created_at": datetime.utcnow(),
    }

    _job_queue[job_id] = job_data

    return JobResponse(
        job_id=job_data["job_id"],
        workflow_id=job_data["workflow_id"],
        execution_id=job_data["execution_id"],
        organization_id=job_data["organization_id"],
        workflow_definition=job_data["workflow_definition"],
        input_data=job_data.get("input_data"),
        timeout_seconds=job_data["timeout_seconds"],
        max_retries=job_data["max_retries"],
        retry_count=job_data["retry_count"],
        priority=job_data["priority"],
        scheduled_for=job_data.get("scheduled_for"),
        status=job_data["status"],
        claimed_by=job_data.get("claimed_by"),
        created_at=job_data["created_at"],
    )


@router.get("/jobs/next")
async def get_next_job(
    worker_id: str,
    capabilities: Optional[str] = None,
    org_id: str = Depends(get_org_id),
):
    """
    Get the next available job for a worker.

    Returns 204 No Content if no jobs are available.
    """
    if worker_id not in _workers:
        raise HTTPException(status_code=404, detail="Worker not registered")

    worker = _workers[worker_id]
    worker_capabilities = set(worker.get("capabilities", []))
    requested_capabilities = set(capabilities.split(",")) if capabilities else set()

    # Find the highest priority pending job
    best_job = None
    best_priority = -float("inf")

    for job_id, job in _job_queue.items():
        if job["status"] != "pending":
            continue
        if job["organization_id"] != org_id:
            continue

        # Check if scheduled for future
        if job.get("scheduled_for") and job["scheduled_for"] > datetime.utcnow():
            continue

        # Check priority
        if job["priority"] > best_priority:
            best_job = job
            best_priority = job["priority"]

    if best_job:
        return {
            "job_id": best_job["job_id"],
            "workflow_id": best_job["workflow_id"],
            "execution_id": best_job["execution_id"],
            "organization_id": best_job["organization_id"],
            "workflow_definition": best_job["workflow_definition"],
            "input_data": best_job.get("input_data"),
            "timeout_seconds": best_job["timeout_seconds"],
            "max_retries": best_job["max_retries"],
            "retry_count": best_job["retry_count"],
            "priority": best_job["priority"],
            "scheduled_for": best_job.get("scheduled_for").isoformat() if best_job.get("scheduled_for") else None,
            "context": best_job.get("context"),
            "metadata": best_job.get("metadata"),
        }

    # No jobs available - return 204
    from fastapi.responses import Response
    return Response(status_code=204)


@router.post("/jobs/{job_id}/claim")
async def claim_job(
    job_id: str,
    claim: JobClaim,
):
    """
    Claim a job for execution.

    Only one worker can claim a job at a time.
    """
    if job_id not in _job_queue:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _job_queue[job_id]

    if job["status"] != "pending":
        raise HTTPException(status_code=409, detail="Job already claimed or completed")

    # Claim the job
    job["status"] = "running"
    job["claimed_by"] = claim.worker_id
    job["claimed_at"] = datetime.utcnow()

    # Update worker status
    if claim.worker_id in _workers:
        _workers[claim.worker_id]["current_job_id"] = job_id
        _workers[claim.worker_id]["status"] = "busy"

    return {"status": "claimed", "job_id": job_id, "worker_id": claim.worker_id}


@router.post("/jobs/{job_id}/result")
async def submit_job_result(
    job_id: str,
    result: JobResult,
):
    """
    Submit the result of job execution.

    Called by workers after completing (or failing) a job.
    """
    if job_id not in _job_queue:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _job_queue[job_id]

    # Update job status
    job["status"] = result.status
    job["completed_at"] = datetime.utcnow()

    # Store result
    _job_results[job_id] = {
        "job_id": job_id,
        "status": result.status,
        "output": result.output,
        "error": result.error,
        "error_traceback": result.error_traceback,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "duration_seconds": result.duration_seconds,
        "tokens_used": result.tokens_used,
        "cost": result.cost,
        "step_results": result.step_results,
        "logs": result.logs,
    }

    # Update worker status
    if job.get("claimed_by") and job["claimed_by"] in _workers:
        worker = _workers[job["claimed_by"]]
        worker["current_job_id"] = None
        worker["status"] = "idle"
        if result.status == "completed":
            worker["jobs_completed"] = worker.get("jobs_completed", 0) + 1
        else:
            worker["jobs_failed"] = worker.get("jobs_failed", 0) + 1

    return {"status": "received", "job_id": job_id}


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job details."""
    if job_id not in _job_queue:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _job_queue[job_id]
    return JobResponse(
        job_id=job["job_id"],
        workflow_id=job["workflow_id"],
        execution_id=job["execution_id"],
        organization_id=job["organization_id"],
        workflow_definition=job["workflow_definition"],
        input_data=job.get("input_data"),
        timeout_seconds=job["timeout_seconds"],
        max_retries=job["max_retries"],
        retry_count=job["retry_count"],
        priority=job["priority"],
        scheduled_for=job.get("scheduled_for"),
        status=job["status"],
        claimed_by=job.get("claimed_by"),
        created_at=job["created_at"],
    )


@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Get job execution result."""
    if job_id not in _job_results:
        raise HTTPException(status_code=404, detail="Result not found")

    return _job_results[job_id]


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    org_id: str = Depends(get_org_id),
    status: Optional[str] = None,
    limit: int = 100,
):
    """List jobs for the organization."""
    jobs = []
    for job in _job_queue.values():
        if job["organization_id"] != org_id:
            continue
        if status and job["status"] != status:
            continue
        jobs.append(JobResponse(
            job_id=job["job_id"],
            workflow_id=job["workflow_id"],
            execution_id=job["execution_id"],
            organization_id=job["organization_id"],
            workflow_definition=job["workflow_definition"],
            input_data=job.get("input_data"),
            timeout_seconds=job["timeout_seconds"],
            max_retries=job["max_retries"],
            retry_count=job["retry_count"],
            priority=job["priority"],
            scheduled_for=job.get("scheduled_for"),
            status=job["status"],
            claimed_by=job.get("claimed_by"),
            created_at=job["created_at"],
        ))

    # Sort by priority (descending) and created_at (ascending)
    jobs.sort(key=lambda j: (-j.priority, j.created_at))

    return jobs[:limit]
