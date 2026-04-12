# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Document Translation Tool is a desktop GUI application for translating Markdown and DITA documents between Chinese and English while preserving document structure. It uses PySide6 for the GUI and supports OpenAI-compatible and Anthropic-compatible API formats.

## Common Commands

### Run the Application
```bash
python app.py
```

### Run Tests
```powershell
# Run all tests
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1

# Run a specific test file
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1 tests/test_markdown_parser.py

# Run a specific test
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1 tests/test_markdown_parser.py::test_function_name
```

### Build Windows Package
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Build output goes to `../releases/windows/DocTranslationTool/` with the executable at `../releases/windows/DocTranslationTool/DocTranslationTool.exe`.

## Architecture

### Entry Point
- `app.py`: Main entry point that calls `doc_translation_tool.app.main()`

### Package Structure
- `doc_translation_tool/`: Main package
  - `app.py`: Application entry with `main()` function, resolves runtime project root
  - `config/`: Configuration loading from `.env` and `settings.json`
  - `documents/`: Document handlers (Markdown, DITA) with registry pattern
  - `llm/`: LLM client implementations (OpenAI and Anthropic formats, mock provider for testing)
  - `markdown/`: Markdown parsing, protection, segmentation, and rebuilding
  - `models/`: Data schemas (TranslationTask)
  - `services/`: Core services (pipeline, task service, validation, caching, glossary loading, batch translation)
  - `ui/`: PySide6 GUI components (main window, dialogs)
  - `utils/`: Utility modules (text processing with performance optimizations)

### Document Handler Registry
Document types are registered via `doc_translation_tool/documents/registry.py`. The registry maps file extensions to document handlers:
- `.md` → MarkdownDocumentHandler
- `.dita` → DitaDocumentHandler

New document types can be added by calling `register_document_format()` with a `DocumentFormatSpec`.

### Configuration Priority
Configuration is loaded from multiple sources (highest priority first):
1. Runtime environment variables
2. `.env` file
3. `settings.json` file
4. Code defaults

Key config files:
- `.env.example`: Template for `.env` with API endpoint, key, model
- `settings.example.json`: Template for advanced settings (batch size, timeouts, validation modes, etc.)
- `glossary.example.json`: Template for glossary entries

New validation configuration options:
- `validation_mode`: Controls validation strictness (strict/balanced/lenient)
- `residual_language_threshold`: Maximum allowed residual source language words
- `allow_placeholder_reorder`: Whether to allow placeholder reordering
- `min_batch_split_size`: Minimum segment count when splitting failed batches

These settings automatically adapt based on document type detection (technical documents use lenient mode by default).

### Translation Pipeline
The translation flow is orchestrated by `DocumentTranslationPipeline` (`services/pipeline.py`):
1. Detect document type from file extension
2. Parse document into translatable segments
3. Protect technical content (placeholders, code, paths, HTML/XML tags, file paths)
4. Load glossary if present
5. Execute batch translation with parallel requests and adaptive validation
6. Handle retries with automatic fallback strategies (batch splitting, single-segment rescue, rate-limit backoff)
7. Support checkpoint caching for resume on failure
8. Rebuild document with translated segments
9. Write output to new file

Key features:
- **Adaptive validation**: Automatically detects document type (technical vs. general) and adjusts validation strictness
- **Smart retry**: Single-segment placeholder rescue, residual language rescue, batch splitting with minimum size control
- **Rate-limit handling**: Automatic concurrency reduction on 429 errors
- **Progress tracking**: Real-time segment-level progress with dynamic time estimation
- **Checkpoint resume**: Automatic caching and resume for large documents

### LLM Client Architecture
`llm/client.py` provides an abstract `BaseLLMClient` with two implementations:
- `OpenAICompatibleClient`: For OpenAI-compatible endpoints
- `AnthropicCompatibleClient`: For Anthropic-compatible endpoints

The client handles batch translation, connectivity checks, and rate-limit backoff.

### Testing
Tests use pytest with PySide6's offscreen platform (`QT_QPA_PLATFORM=offscreen`).
Test fixtures are in `tests/fixtures/` including regression samples for Markdown and DITA.

## Version Management

Version is defined in `doc_translation_tool/__init__.py` as `__version__`. Update this when releasing:
1. Update `doc_translation_tool/__init__.py`
2. Append release notes to `CHANGELOG.md`
3. Rebuild Windows package

## Key Dependencies

- PySide6 >= 6.7: GUI framework
- httpx >= 0.28: HTTP client for LLM API calls
- python-dotenv >= 1.0: Environment file loading
- pytest >= 8.0: Testing (dev)
- pyinstaller >= 6.17: Windows packaging (build)
