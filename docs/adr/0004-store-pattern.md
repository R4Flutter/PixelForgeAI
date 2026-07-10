# ADR 0004: Redux-Inspired Store for State Management

## Status
Accepted

## Context
The application initially used mutable global state via `core/app_state.py` and scattered `@property` fields on service objects. This approach has several drawbacks:
- State changes are untraceable
- No single source of truth
- Race conditions between concurrent state mutations
- Difficult to test components that depend on state

## Decision
Adopt a Redux-inspired unidirectional data flow pattern:

1. **Store[T]** — Holds immutable state, exposes `state` property (returns deep copy)
2. **Action** — Describes a state change (type + payload)
3. **Reducer[T]** — Pure function `(state, action) -> new_state`
4. **dispatch(action)** — The only way to modify state
5. **subscribe(listener)** — React to state changes

Separate stores for distinct domains:
- **AppStore** — Navigation, theme, processing flag
- **ProcessingStore** — Job progress, pause state, failed files
- **SettingsStore** — User configuration
- **SessionStore** — Recent projects, window geometry, license status

## Trade-offs
- (+) Predictable state updates
- (+) Time-travel debugging capability
- (+) Easy to test (reducers are pure functions)
- (-) Boilerplate for simple state changes
- (-) Deep copy on every state read has performance cost (acceptable for UI-scale state)

## Consequences
- Mutable `core/app_state.py` should be deprecated in favor of stores
- All components should consume state via store subscriptions
- State mutations only through dispatched actions
- Stores are registered in Dependency container
