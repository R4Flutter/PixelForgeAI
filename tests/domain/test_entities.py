from __future__ import annotations

from domain.entities.image import Image, ImageKind, OutputImage
from domain.entities.pipeline_job import PipelineJob, JobStatus, Stage, StageType
from domain.entities.history_entry import HistoryEntry


class TestImage:
    def test_create_image(self) -> None:
        img = Image(path="/tmp/test.png", file_name="test.png", file_size=1024, width=100, height=200)
        assert img.path == "/tmp/test.png"
        assert img.file_name == "test.png"
        assert img.file_size == 1024
        assert img.width == 100
        assert img.height == 200
        assert img.kind == ImageKind.UNKNOWN

    def test_extension_property(self) -> None:
        img = Image(path="/tmp/test.png", file_name="test.png", file_size=1024)
        assert img.extension == ".png"

    def test_supported_extensions(self) -> None:
        img = Image(path="/tmp/test.jpg", file_name="test.jpg", file_size=1024)
        assert img.is_supported

        img2 = Image(path="/tmp/test.gif", file_name="test.gif", file_size=1024)
        assert not img2.is_supported


class TestOutputImage:
    def test_create_output(self) -> None:
        source = Image(path="/tmp/test.png", file_name="test.png", file_size=1024)
        output = OutputImage(source=source, output_path="/output/test.png", succeeded=True)
        assert output.source == source
        assert output.succeeded


class TestPipelineJob:
    def test_create_job(self) -> None:
        img = Image(path="/tmp/test.png", file_name="test.png", file_size=1024)
        job = PipelineJob(job_id="test-1", images=[img])
        assert job.job_id == "test-1"
        assert job.status == JobStatus.QUEUED
        assert job.total == 1

    def test_progress_calculation(self) -> None:
        img = Image(path="/tmp/test.png", file_name="test.png", file_size=1024)
        stages = [Stage(type=StageType.REMOVE_BG, success=True)]
        job = PipelineJob(job_id="test-1", images=[img], stages=[Stage(type=StageType.LOAD, success=False)])
        assert job.progress == 0

    def test_stage_labels(self) -> None:
        assert StageType.REMOVE_BG.label == "Remove Background"
        assert StageType.UPSCALE.label == "Upscaling"
        assert StageType.RESIZE.label == "Resizing"


class TestHistoryEntry:
    def test_create_entry(self) -> None:
        img = Image(path="/tmp/test.png", file_name="test.png", file_size=1024)
        job = PipelineJob(job_id="test-1", images=[img])
        entry = HistoryEntry(job=job, outputs=[])
        assert entry.job.job_id == "test-1"
