# STEGOSIGHT

STEGOSIGHT is a PyQt6 desktop interface for experimenting with modern steganography workflows. This repository ships with a redesigned, modular GUI scaffold and mock implementations so that the core engines can be wired in later.

## Features

- Navigation sidebar with quick access to Embed, Extract, Analyze, Neutralize, Settings, and History views.
- Non-blocking long-running tasks via a shared `QThreadPool` and reusable worker wrapper.
- Drag-and-drop file pickers, progress dialogs with cancellation, and toast-style status messages.
- Mock engines that keep the interface functional until production services are integrated.
- CLI stub: `python -m stegosight.app --cli <files>` for headless risk scanning.

## Project Layout

```
stegosight/
  core/         # Protocols and shared dataclasses
  ui/           # Main window, views, widgets, and assets
  utils/        # Threading helpers, validators, theming, i18n stubs
  app.py        # GUI + CLI entry point with mock engines
```

## Getting Started

1. **Install dependencies** (Python 3.11 recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the GUI**:

   ```bash
   python -m stegosight.app
   ```

3. **Run in CLI mode**:

   ```bash
   python -m stegosight.app --cli /path/to/media
   ```

4. **Run tests**:

   ```bash
   pytest
   ```

## Plugging In Real Engines

- Implement classes satisfying the protocols in `stegosight/core/*`.
- Update `stegosight/app.py` to instantiate your concrete implementations instead of the mock classes.
- Extend the views as needed; they already emit and consume operation results for history tracking.

## Packaging

- Dependencies are listed in `requirements.txt`. PyInstaller builds are supported; point the entry script to `stegosight/app.py`.
