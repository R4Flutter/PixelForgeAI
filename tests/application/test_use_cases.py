from __future__ import annotations

from unittest.mock import MagicMock

from common.result import Success
from application.use_cases.base import UseCase


class TestUseCaseBase:
    def test_use_case_abc_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            UseCase()

    def test_use_case_returns_result(self) -> None:
        use_case = MagicMock(spec=UseCase)
        use_case.execute.return_value = Success("done")
        result = use_case.execute(None)
        assert result.is_success


class TestStartPipelineUseCase:
    def test_execute_returns_success(self, event_bus) -> None:
        from application.use_cases.pipeline_use_cases import (
            StartPipelineUseCase,
            StartPipelineRequest,
        )
        use_case = StartPipelineUseCase(event_bus)
        request = StartPipelineRequest(paths=["/tmp/test.png"], settings={})
        result = use_case.execute(request)
        assert result.is_success


class TestCancelPipelineUseCase:
    def test_execute_emits_event(self, event_bus) -> None:
        from application.use_cases.pipeline_use_cases import CancelPipelineUseCase, CancelPipelineRequest
        use_case = CancelPipelineUseCase(event_bus)
        result = use_case.execute(CancelPipelineRequest(job_id="test-1"))
        assert result.is_success


class TestExportImagesUseCase:
    def test_execute_returns_count(self, event_bus) -> None:
        from application.use_cases.export_use_cases import ExportImagesUseCase, ExportRequest
        use_case = ExportImagesUseCase(event_bus)
        request = ExportRequest(source_paths=[], output_dir="/tmp")
        result = use_case.execute(request)
        assert result.is_success


class TestGenerateThumbnailUseCase:
    def test_execute_returns_response(self, event_bus) -> None:
        from application.use_cases.thumbnail_use_cases import (
            GenerateThumbnailUseCase,
            GenerateThumbnailRequest,
        )
        use_case = GenerateThumbnailUseCase(event_bus)
        request = GenerateThumbnailRequest(image_path="/nonexistent.png")
        result = use_case.execute(request)
        assert result.is_success


class TestNavigatePageUseCase:
    def test_execute_updates_store(self, event_bus, app_store) -> None:
        from application.use_cases.navigation_use_cases import NavigatePageUseCase, NavigatePageRequest
        use_case = NavigatePageUseCase(app_store, event_bus)
        result = use_case.execute(NavigatePageRequest(page_index=2))
        assert result.is_success


import pytest
