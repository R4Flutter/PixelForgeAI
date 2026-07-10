from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.enums import PipelineStage


@dataclass
class StageResult:
    stage: PipelineStage
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
