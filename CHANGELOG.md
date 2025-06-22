# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Store and cancel timers on shutdown for smooth cleanup.
- Handle camera feed timeouts and avoid duplicate webcam pages.
- Cancel experiment timer on shutdown.
- Use `set_text` for recording menu labels.
- Run UVC tasks concurrently and check camera status.
- Improve error handling during startup and when toggling cameras.
- Add motion status callback and tests.
- Wrap camera start/stop operations in try/except blocks.
- Fix log viewer error caused by removed `last_args` attribute in NiceGUI `ScrollArea`.
