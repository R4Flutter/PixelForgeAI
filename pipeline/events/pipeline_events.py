from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class StageChangedData:
    stage: str
    index: int
    timestamp: float = 0.0


@dataclass
class ProgressData:
    done: int
    total: int
    current_file: str
    percentage: float = 0.0


@dataclass
class ImageResultData:
    source_path: str
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class PipelineEvent:
    job_id: str
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
