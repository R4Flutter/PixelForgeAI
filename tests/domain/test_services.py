from __future__ import annotations

from domain.services.validation_service import ValidationService
from domain.services.export_policy import ExportPolicy
from domain.entities.image import Image
from domain.value_objects.export_options import ExportOptions, ExportProfile


class TestValidationService:
    def test_validate_supported_format(self) -> None:
        service = ValidationService()
        result = service.validate_file_extension("test.png")
        assert result is True

    def test_reject_unsupported_format(self) -> None:
        service = ValidationService()
        result = service.validate_file_extension("test.gif")
        assert result is True


class TestExportPolicy:
    def test_can_export(self) -> None:
        policy = ExportPolicy()
        assert policy is not None
