# ADR 0003: Feature-First Module Architecture

## Status
Accepted

## Context
The initial architecture placed all GUI code in a flat `gui/` directory with feature controllers in `features/` serving as thin wrappers. As the application grows, this creates several problems:
- GUI pages become monoliths (home.py: 883 lines, processing.py: 859 lines)
- Feature logic is scattered between gui/, features/, and services/
- New features require changes across multiple directories
- Unclear ownership for new developers

## Decision
Organize code by feature domain instead of by layer.

Each feature module (`features/<feature>/`) owns its complete implementation:
- `ui/` — Qt widgets specific to this feature
- `controller.py` — Event wiring and orchestration
- `commands.py` — Feature-specific commands
- `events.py` — Feature-specific event types
- `state.py` — Feature-specific immutable state

The existing `gui/` directory remains for shared pages. Over time, as features mature, their UI moves from `gui/` into `features/<feature>/ui/`.

## Trade-offs
- (+) Clear ownership and discovery
- (+) Easier to add new features without touching existing code
- (+) Better alignment with team structure
- (-) Some code duplication across features (mitigated by shared components/)
- (-) Requires discipline to keep shared code in components/

## Consequences
- Feature modules are wired in `bootstrap.py`
- Feature controllers subscribe to EventBus events
- Features expose their state for testing
- Cross-cutting UI widgets remain in components/
