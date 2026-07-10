from __future__ import annotations

from typing import List, Optional, Protocol

from application.interfaces.services import (
    PipelineServiceProtocol,
    ExportServiceProtocol,
    ImageServiceProtocol,
)
from application.interfaces.repositories import (
    SettingsRepositoryProtocol,
    ImageRepositoryProtocol,
    CacheRepositoryProtocol,
)


def test_pipeline_service_protocol() -> None:
    assert isinstance(PipelineServiceProtocol, type)


def test_export_service_protocol() -> None:
    assert isinstance(ExportServiceProtocol, type)


def test_image_service_protocol() -> None:
    assert isinstance(ImageServiceProtocol, type)


def test_settings_repository_protocol() -> None:
    assert isinstance(SettingsRepositoryProtocol, type)


def test_image_repository_protocol() -> None:
    assert isinstance(ImageRepositoryProtocol, type)


def test_cache_repository_protocol() -> None:
    assert isinstance(CacheRepositoryProtocol, type)
