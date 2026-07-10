from __future__ import annotations

from commands.base import CommandDispatcher
from events.base import EventBus
from plogging.logger import get_logger

from dependency import Dependency

from application.use_cases.pipeline_use_cases import (
    StartPipelineUseCase,
    CancelPipelineUseCase,
    PausePipelineUseCase,
    ResumePipelineUseCase,
)
from application.use_cases.export_use_cases import ExportImagesUseCase
from application.use_cases.settings_use_cases import LoadSettingsUseCase, SaveSettingsUseCase
from application.use_cases.thumbnail_use_cases import GenerateThumbnailUseCase
from application.use_cases.history_use_cases import AddHistoryEntryUseCase, LoadHistoryUseCase, ClearHistoryUseCase
from application.use_cases.navigation_use_cases import NavigatePageUseCase, SetProcessingStateUseCase
from application.use_cases.pipeline_retry_use_case import RetryPipelineUseCase
from application.interfaces.repositories import SettingsRepositoryProtocol
from application.interfaces.services import (
    PipelineServiceProtocol,
    ExportServiceProtocol,
    ImageServiceProtocol,
)

from infrastructure.cache.disk_cache import DiskCache
from infrastructure.thumbnails.thumbnail_generator import ThumbnailGenerator
from infrastructure.filesystem.file_operations import FileOperations
from infrastructure.persistence.settings_repository import SettingsRepository

from plugins.manager import PluginManager

from store.app_store import AppStore
from store.processing_store import ProcessingStore
from store.settings_store import SettingsStore
from store.session_store import SessionStore

from services.history_service import HistoryService

log = get_logger(__name__)


def bootstrap() -> Dependency:
    di = Dependency()

    # --- Events & Commands ---
    event_bus = EventBus()
    dispatcher = CommandDispatcher(event_bus)

    di.register("event_bus", event_bus)
    di.register("dispatcher", dispatcher)

    # --- Stores ---
    app_store = AppStore()
    processing_store = ProcessingStore()
    settings_store = SettingsStore()
    session_store = SessionStore()

    di.register("app_store", app_store)
    di.register("processing_store", processing_store)
    di.register("settings_store", settings_store)
    di.register("session_store", session_store)

    # --- Infrastructure ---
    cache = DiskCache()
    file_ops = FileOperations()
    thumbnail_gen = ThumbnailGenerator(cache)
    settings_repo: SettingsRepositoryProtocol = SettingsRepository()

    di.register("cache", cache)
    di.register("file_ops", file_ops)
    di.register("thumbnail_service", thumbnail_gen)
    di.register("settings_repository", settings_repo)

    # --- Plugin System ---
    plugin_manager = PluginManager()
    di.register("plugin_manager", plugin_manager)

    # --- Services ---
    history_service = HistoryService(event_bus)
    di.register("history_service", history_service)

    # --- Use Cases ---
    start_pipeline = StartPipelineUseCase(event_bus)
    cancel_pipeline = CancelPipelineUseCase(event_bus)
    pause_pipeline = PausePipelineUseCase(event_bus)
    resume_pipeline = ResumePipelineUseCase(event_bus)
    export_images = ExportImagesUseCase(event_bus)
    load_settings = LoadSettingsUseCase(event_bus)
    save_settings = SaveSettingsUseCase(event_bus)
    generate_thumbnail = GenerateThumbnailUseCase(event_bus)
    add_history_entry = AddHistoryEntryUseCase(event_bus)
    load_history = LoadHistoryUseCase(event_bus)
    clear_history = ClearHistoryUseCase(event_bus)
    navigate_page = NavigatePageUseCase(app_store, event_bus)
    set_processing_state = SetProcessingStateUseCase(app_store)
    retry_pipeline = RetryPipelineUseCase(event_bus)

    di.register("start_pipeline_use_case", start_pipeline)
    di.register("cancel_pipeline_use_case", cancel_pipeline)
    di.register("pause_pipeline_use_case", pause_pipeline)
    di.register("resume_pipeline_use_case", resume_pipeline)
    di.register("export_images_use_case", export_images)
    di.register("load_settings_use_case", load_settings)
    di.register("save_settings_use_case", save_settings)
    di.register("generate_thumbnail_use_case", generate_thumbnail)
    di.register("add_history_entry_use_case", add_history_entry)
    di.register("load_history_use_case", load_history)
    di.register("clear_history_use_case", clear_history)
    di.register("navigate_page_use_case", navigate_page)
    di.register("set_processing_state_use_case", set_processing_state)
    di.register("retry_pipeline_use_case", retry_pipeline)

    log.info("Application bootstrapped successfully")
    return di
