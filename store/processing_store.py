from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from store.base import Action, Reducer, Store


@dataclass
class ProcessingState:
    job_id: str = ""
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_file: str = ""
    current_stage: str = ""
    percentage: float = 0.0
    is_running: bool = False
    is_paused: bool = False
    failed_files: List[str] = field(default_factory=list)


def processing_reducer(state: ProcessingState, action: Action) -> ProcessingState:
    p = action.payload
    if action.type == "PROCESSING_START":
        return ProcessingState(job_id=p.get("job_id", ""), total=p.get("total", 0), is_running=True)
    if action.type == "PROCESSING_PROGRESS":
        return ProcessingState(
            job_id=state.job_id, total=state.total, completed=p.get("completed", state.completed),
            failed=state.failed, current_file=p.get("file", ""), current_stage=p.get("stage", ""),
            percentage=p.get("percentage", 0.0), is_running=True, is_paused=state.is_paused,
            failed_files=state.failed_files,
        )
    if action.type == "PROCESSING_PAUSE":
        return ProcessingState(job_id=state.job_id, total=state.total, completed=state.completed,
            failed=state.failed, is_running=True, is_paused=True, failed_files=state.failed_files)
    if action.type == "PROCESSING_RESUME":
        return ProcessingState(job_id=state.job_id, total=state.total, completed=state.completed,
            failed=state.failed, is_running=True, is_paused=False, failed_files=state.failed_files)
    if action.type == "PROCESSING_COMPLETE":
        return ProcessingState(job_id=state.job_id, total=state.total, completed=state.completed,
            failed=state.failed, is_running=False, failed_files=state.failed_files)
    if action.type == "PROCESSING_RESET":
        return ProcessingState()
    return state


class ProcessingStore(Store[ProcessingState]):
    def __init__(self) -> None:
        super().__init__(ProcessingState(), processing_reducer)
