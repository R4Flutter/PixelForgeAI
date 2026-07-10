# ADR-0002: Use Protocols for Dependency Injection

## Status
Accepted

## Context
We need to decouple application logic from infrastructure without a DI framework.

## Decision
Use Python `Protocol` classes for dependency interfaces. Infrastructure classes
implement these protocols implicitly via structural subtyping.

## Consequences
- No framework dependency
- Static type checking catches wiring errors
- Simple to mock in tests
