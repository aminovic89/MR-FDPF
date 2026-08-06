"""Minimal in-memory background job runner for long simulations.

A single-process, in-memory dict is enough for a local dev tool (no need
for Celery/Redis here); jobs run in daemon threads so the FastAPI event
loop stays free to serve progress-polling requests while a simulation is
running -- that's the whole point of this module, since a plain blocking
endpoint would freeze the server (including its own polling endpoint)
for the entire simulation.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending | running | done | error
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    with _lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def run_in_background(job: Job, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    def _progress(fraction: float, message: str) -> None:
        job.progress = fraction
        job.message = message

    def _run() -> None:
        job.status = "running"
        try:
            job.result = fn(*args, progress_callback=_progress, **kwargs)
            job.progress = 1.0
            job.status = "done"
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            job.error = str(exc)
            job.status = "error"

    threading.Thread(target=_run, daemon=True).start()
