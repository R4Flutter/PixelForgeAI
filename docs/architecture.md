# PixelForgeAI Architecture

## Layered Dependency Rule

Dependency direction points inward. Inner layers never import from outer layers.

```
Presentation (Qt GUI Pages)
    ↓
Feature Modules (Controllers, State, Events)
    ↓
Commands (User Action Commands)
    ↓
Use Cases (Application Logic)
    ↓
Application Services / Interfaces (Protocols)
    ↓
Domain (Entities, Value Objects, Services, Rules)
    ↓
Repositories (Data Access Protocols)
    ↓
Infrastructure (AI, Filesystem, Cache, Persistence, Logging)
```

Cross-cutting layers (available to all):
- Events (EventBus publish/subscribe)
- Store (Redux-like state management)
- Design System (Design tokens, themes, components)
- Plugins (Extensibility system)
- Configuration (Settings loading/saving)
- Logging (Structured logging)

## Layer Overview

### Domain (`domain/`)
Core business logic. Zero dependencies on Qt, filesystem, or AI frameworks.
- `entities/` — Image, PipelineJob, HistoryEntry, OutputImage
- `value_objects/` — ExportOptions, PipelineStatistics, ProcessingResult, PipelineFlow
- `services/` — ValidationService, ExportPolicy
- `rules/` — NamingRules, ProcessingRules

### Application (`application/`)
Orchestrates domain objects to fulfill use cases. Depends only on domain and protocols.
- `use_cases/` — StartPipeline, CancelPipeline, PausePipeline, ResumePipeline, ExportImages, GenerateThumbnail, Load/Save Settings, Load/Clear History, NavigatePage, RetryPipeline
- `interfaces/` — Repository and service protocols (PipelineServiceProtocol, ExportServiceProtocol, ImageServiceProtocol, SettingsRepositoryProtocol, ImageRepositoryProtocol, CacheRepositoryProtocol)
- `services/` — Reserved for future application-level service implementations

### Features (`features/`)
Feature-first modules owning their complete implementation.
- `home/` — Image selection, drag-drop, pipeline initiation
- `processing/` — Pipeline progress, pause/resume/cancel
- `results/` — Pipeline completion summary, export
- `settings/` — Application configuration
- `history/` — Pipeline run history

Each feature contains:
- `__init__.py` — Feature class exposing controller and state
- `controller.py` — Wires GUI events to commands and use cases
- `state.py` — Feature-specific state dataclass
- `events.py` — Feature-specific event types
- `commands.py` — Feature-specific command types

### Presentation (`gui/`)
PySide6 Qt widgets.
- Pages: HomePage, ProcessingPage, ResultsPage, SettingsPage, AboutPage, SplashScreen
- Components: Buttons, Cards, Progress, Icons, Carousel
- Wiring: MainWindow with sidebar navigation and crossfade transitions

### Commands (`commands/`)
Command pattern for user actions. Commands call use cases.
- `base.py` — Command ABC, CommandResult, CommandDispatcher
- `pipeline_commands.py` — Start, Cancel, Pause, Resume
- `export_commands.py` — Export, Open folder
- `settings_commands.py` — Change, Load, Save

### Events (`events/`)
Typed event system. Decouples UI from business logic.
- `base.py` — Event dataclass, EventBus (publish/subscribe)
- `pipeline_events.py` — Pipeline lifecycle events
- `image_events.py` — Image selection events
- `settings_events.py` — Settings change events
- `export_events.py` — Export lifecycle events
- `history_events.py` — History management events

### Store (`store/`)
Redux-like state management with typed stores.
- `base.py` — Store[T], Action, Reducer[T]
- `app_store.py` — AppState (current page, theme, processing flag)
- `processing_store.py` — ProcessingState (job progress, pause state)
- `settings_store.py` — SettingsState (configuration values)
- `session_store.py` — SessionState (recent projects, window geometry)

### Infrastructure (`infrastructure/`)
Implements protocols defined in application layer. Handles all I/O.
- `ai/` — RealESRGAN upscaler, Rembg background remover
- `filesystem/` — File operations (atomic writes, copies)
- `cache/` — Disk cache (MD5-keyed file cache)
- `thumbnails/` — Thumbnail generation
- `persistence/` — Settings repository implementation

### Plugins (`plugins/`)
Plugin system for extensibility.
- `base.py` — Plugin ABC, PluginMeta
- `interfaces.py` — PipelinePlugin, ExportPlugin, ImagePlugin, SettingsPlugin
- `registry.py` — PluginRegistry (singleton)
- `manager.py` — PluginManager (load/unload/shutdown)

### Pipeline (`pipeline/`)
Processing pipeline orchestration.
- `core/` — PipelineOrchestrator, StageExecutor
- `stages/` — RemoveBgStage, UpscaleStage, ResizeStage
- `validators/` — ImageValidator
- `events/` — PipelineEvent types
- `models/` — PipelineResult, StageResult

### Configuration (`config/`)
Settings loading/saving, constants.
- paths, pipeline, defaults, performance, appearance, export, licensing

### Logging (`logging/`)
Structured logging setup.
- logger, handlers, formatter, filters

### Design System (`design_system/`)
Design tokens, theme definitions.
- `tokens/` — colors, typography, spacing, elevation
- `themes/` — DarkTheme, LightTheme

## Data Flow

### Image Processing Session
1. User drops images on HomePage (GUI)
2. HomeController creates StartPipelineCommand → dispatches via CommandDispatcher
3. Command emits PipelineStartedEvent on EventBus
4. PipelineOrchestrator runs stages: RemoveBg → Upscale → Resize
5. Progress emitted as events → ProcessingStore state updates → GUI reactively updates
6. On completion, PipelineCompletedEvent emitted → ResultsPage shows summary
7. HistoryEntry added via HistoryService

### Settings Change
1. User changes setting in SettingsPage
2. SettingsController creates ChangeSettingCommand
3. Command emits SettingsChangedEvent
4. SettingsStore state updates
5. SettingsRepository persists to disk

## Dependency Injection

The `Dependency` singleton (wired in `bootstrap.py`) registers:
- EventBus, CommandDispatcher
- Stores (App, Processing, Settings, Session)
- Infrastructure (cache, file_ops, thumbnail, settings repository)
- Services (history)
- Use Cases (pipeline, export, settings, thumbnail, history, navigation)
- PluginManager

## File Size Limits

- UI pages ≤ 500 lines
- Services ≤ 400 lines
- Commands ≤ 200 lines
- Use Cases ≤ 200 lines
- Components ≤ 250 lines

## Plugin Architecture

Plugins implement one of:
- `PipelinePlugin` — Custom pipeline stages
- `ExportPlugin` — Custom export formats
- `ImagePlugin` — Image metadata processors
- `SettingsPlugin` — Custom settings pages

Each plugin is loaded by PluginManager and registered in PluginRegistry.
