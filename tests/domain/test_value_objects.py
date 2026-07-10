from __future__ import annotations

from domain.value_objects.export_options import ExportOptions, ExportProfile
from domain.value_objects.pipeline_statistics import PipelineStatistics
from domain.value_objects.processing_result import ProcessingResult
from domain.value_objects.pipeline_flow import PipelineFlow
from domain.entities.pipeline_job import StageType


class TestExportProfile:
    def test_default_profile(self) -> None:
        profile = ExportProfile()
        assert profile.output_format == "png"
        assert profile.quality == 95

    def test_custom_profile(self) -> None:
        profile = ExportProfile(output_format="jpg", quality=80)
        assert profile.output_format == "jpg"
        assert profile.quality == 80


class TestExportOptions:
    def test_default_options(self) -> None:
        options = ExportOptions()
        assert options.output_dir == "output/final"
        assert options.profile.output_format == "png"


class TestPipelineStatistics:
    def test_default_stats(self) -> None:
        stats = PipelineStatistics()
        assert stats.total_images == 0
        assert stats.all_succeeded is False

    def test_success_rate(self) -> None:
        stats = PipelineStatistics(total_images=10, succeeded=8, failed=2)
        assert stats.success_rate == 0.8

    def test_all_succeeded(self) -> None:
        stats = PipelineStatistics(total_images=5, succeeded=5)
        assert stats.all_succeeded


class TestProcessingResult:
    def test_success_result(self) -> None:
        result = ProcessingResult(success=True, image_path="/tmp/test.png")
        assert result.success
        assert result.output_path is None

    def test_failure_result(self) -> None:
        result = ProcessingResult(success=False, image_path="/tmp/test.png", error="Failed")
        assert not result.success
        assert result.error == "Failed"


class TestPipelineFlow:
    def test_default_flow(self) -> None:
        flow = PipelineFlow()
        assert flow.count == 4
        assert flow.stages[0] == StageType.REMOVE_BG

    def test_stage_index(self) -> None:
        flow = PipelineFlow()
        assert flow.index_of(StageType.UPSCALE) == 1
        assert flow.index_of(StageType.LOAD) == -1
