# Changelog

## [0.2.2] - 2026-02-22

### Changed
- Documented single worker process requirement in README

## [0.2.0] - 2026-02-22

### Added
- Presence callbacks can now return signals alongside HTML
  - `str` — HTML only (existing behaviour, backwards compatible)
  - `dict` — signals only
  - `(str, dict)` — HTML + signals
  - `(None, dict)` — signals only (tuple form)

## [0.1.0] - 2026-02-22

### Added
- Channel-based SSE broadcasting over Datastar
- `broadcast()` / `broadcast.elements()` for sending HTML patches
- `broadcast.signals()` for sending signal patches
- `broadcast.connect()` with automatic presence tracking
- `broadcast.disconnect()` and `broadcast.kill()` for connection management
- Presence callbacks with user connect/disconnect notifications
- Heartbeat keep-alive for SSE streams
