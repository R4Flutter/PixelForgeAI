# ADR 0005: Pure Domain Layer with Zero External Dependencies

## Status
Accepted

## Context
Business logic was initially mixed with infrastructure concerns (filesystem access, AI model calls, Qt imports) throughout the codebase. This made it difficult to:
- Unit test business rules without mocking infrastructure
- Reason about business logic independently
- Swap infrastructure implementations
- Understand the core domain model

## Decision
Create a `domain/` package with strict rules:
- Zero dependencies on external packages (no PySide6, no PIL, no OpenCV, no rembg)
- Zero imports from any other project layer
- Uses only Python stdlib, dataclasses, and the `common/` package

Domain structure:
- `entities/` — Core business objects with identity (Image, PipelineJob, HistoryEntry)
- `value_objects/` — Immutable value types (ExportOptions, PipelineStatistics, ProcessingResult)
- `services/` — Domain services with business rules (ValidationService, ExportPolicy)
- `rules/` — Business rule definitions (NamingRules, ProcessingRules)

The `models/` directory (legacy) is maintained as re-exports from `domain/` for backward compatibility.

## Trade-offs
- (+) Business logic is independently testable
- (+) New developers can understand the domain without reading infrastructure code
- (+) Infrastructure changes don't affect business rules
- (-) Some entity-relational impedance (domain objects must be mapped to persistence)
- (-) Cross-cutting concerns (like logging) require careful abstraction

## Consequences
- Domain entities use only Python dataclasses
- Domain services accept and return domain types only
- Validation rules live in domain, not in GUI or infrastructure
- All domain models are frozen/immutable where possible
- Every team member can contribute to domain without understanding the full stack
