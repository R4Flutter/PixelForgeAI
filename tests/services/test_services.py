from __future__ import annotations

from services.history_service import HistoryService, HistoryEntry
from services.image_service import ImageService
from services.export_service import ExportService


class TestHistoryService:
    def test_add_entry(self, event_bus) -> None:
        service = HistoryService(event_bus)
        entry = HistoryEntry(job_id="test-1", total=5, succeeded=5, failed=0)
        service.add(entry)
        recent = service.recent(10)
        assert len(recent) == 1
        assert recent[0].job_id == "test-1"

    def test_recent_returns_empty(self, event_bus) -> None:
        service = HistoryService(event_bus)
        assert service.recent(10) == []

    def test_clear(self, event_bus) -> None:
        service = HistoryService(event_bus)
        entry = HistoryEntry(job_id="test-1", total=5, succeeded=5, failed=0)
        service.add(entry)
        service.clear()
        assert service.recent(10) == []

    def test_max_entries(self, event_bus) -> None:
        service = HistoryService(event_bus)
        for i in range(60):
            service.add(HistoryEntry(job_id=f"test-{i}", total=1, succeeded=1, failed=0))
        assert len(service.recent(100)) == 50


class TestImageService:
    def test_add_valid_files(self, event_bus) -> None:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(b"test")
        tmp.close()

        service = ImageService(event_bus)
        result = service.add([tmp.name])
        assert len(result) == 1

    def test_add_invalid_path(self, event_bus) -> None:
        service = ImageService(event_bus)
        result = service.add(["/nonexistent/file.png"])
        assert len(result) == 0


class TestExportService:
    def test_export_empty_list(self, event_bus) -> None:
        service = ExportService(event_bus)
        count = service.export([], "/tmp")
        assert count == 0
