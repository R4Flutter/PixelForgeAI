from __future__ import annotations

from pipeline.core.orchestrator import PipelineOrchestrator
from pipeline.core.executor import StageExecutor
from pipeline.validators.image_validator import ImageValidator


class TestStageExecutor:
    def test_create_executor(self) -> None:
        executor = StageExecutor()
        assert executor is not None


class TestImageValidator:
    def test_validate_nonexistent(self) -> None:
        validator = ImageValidator()
        result = validator.validate("/nonexistent/path.png")
        assert not result

    def test_validate_empty_path(self) -> None:
        validator = ImageValidator()
        result = validator.validate("")
        assert not result


class TestPipelineOrchestrator:
    def test_create_orchestrator(self) -> None:
        orchestrator = PipelineOrchestrator({})
        assert orchestrator is not None
