# ADR-0001: Use Layered Architecture

## Status
Accepted

## Context
The codebase grew organically with mixed concerns. We need a clear separation
of concerns to improve testability, maintainability, and onboarding.

## Decision
Adopt a layered architecture with strict dependency direction (inward-pointing).

## Consequences
- Domain has zero external dependencies
- Infrastructure implements protocols, not concrete imports
- Tests can mock infrastructure at protocol boundaries
- New features follow a predictable location pattern
