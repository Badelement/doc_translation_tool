# Document Translation Tool

Desktop tool for translating Markdown or DITA documents between Chinese and English while preserving document structure.

[English](./README.md) | [使用指南（中文）](./使用指南.md)

Current local version: `v0.4.6`

## Overview

This project focuses on a practical internal workflow:

- Translate one Markdown or DITA document, or translate supported files from one source directory in one task
- Preserve Markdown structure or DITA XML text structure during translation
- Support both Chinese-to-English and English-to-Chinese translation
- Support OpenAI-compatible and Anthropic-compatible API formats
- Support batch parallel translation for better large-document throughput
- Provide clearer GUI feedback for model configuration, connectivity, and batch progress

## What It Does

- Translate one `.md` or `.dita` file, or scan one source directory for supported files in one task
- Support `zh_to_en` and `en_to_zh`
- Auto-detect common Chinese or English source files and switch the translation direction accordingly
- Provide a directory-batch GUI mode that scans one source directory, auto-detects each file direction, and translates files sequentially
- Support both OpenAI-compatible and Anthropic-compatible API formats
- Support configurable batch-level parallel translation
- Show startup model-config status before a translation run begins
- Show translation progress with batch-based running and completion states
- Preserve Markdown structure, protected placeholders, tables and front matter rules
- Preserve DITA XML text nodes while leaving code-like tags and protected literals stable
- Protect embedded HTML/XML-style tags, common technical file names, path literals, and uppercase technical constants
- Resume large translation runs from cached segment results after a failure
- Reduce concurrency automatically after `429` / rate-limit errors during parallel batch translation
- Write output to a new file instead of overwriting the source file

## Quick Start

### Windows

1. Extract the full `DocTranslationTool-win64.zip` to a normal folder
2. Open the extracted runtime folder that contains `DocTranslationTool.exe`, `_internal\`, and `.env`
3. If you are using the workspace build output instead of the zip, the equivalent folder is `..\releases\windows\DocTranslationTool\`
4. Edit `.env` and fill in your own `DOC_TRANS_BASE_URL`, `DOC_TRANS_API_KEY`, and `DOC_TRANS_MODEL`
5. Launch `DocTranslationTool.exe`

### macOS

1. Extract the full `DocTranslationTool-macos.zip` to a normal folder
2. Open the extracted folder that contains `DocTranslationTool.app` and `.env`
3. Edit `.env` and fill in your own `DOC_TRANS_BASE_URL`, `DOC_TRANS_API_KEY`, and `DOC_TRANS_MODEL`
4. Double-click `DocTranslationTool.app` to launch
5. If macOS blocks the app (security warning), right-click the app, select "Open", then click "Open" in the dialog

### Running from Source (All Platforms)

```bash
# Install dependencies
python3 -m pip install -e .

# Copy and edit configuration
cp .env.example .env
# Edit .env with your API credentials

# Run the application
python3 app.py
```

### Using the Application

1. Check the bottom-left model status first:
   - `配置不完整` means the key fields are missing
   - `配置已加载，待检查连通性` means the config is present and the real API check will happen when translation starts
2. Choose `Single File` or `Directory Batch` mode in the GUI
3. Select one `.md` / `.dita` file, or choose one source directory and an output directory
4. For single-file runs, the tool may auto-switch the direction when it confidently detects Chinese or English source content
5. Start translation and watch the batch-based progress updates

In directory-batch mode, supported `.md` / `.dita` files are scanned and processed sequentially in filename order with one final summary. Each file is auto-detected independently; the GUI direction selector is only used as the fallback for files whose language cannot be determined confidently.

Most users do not need to edit any other config fields.

## Complex Technical Documents

The tool is now tuned more aggressively for large technical Markdown documents and DITA topics that contain heavy tables, paths, config snippets, and mixed technical literals.

Recent reliability improvements include:

- Split overlong table rows more safely, especially when cells contain many `<br>`-separated values
- Protect embedded HTML/XML-style tags so tag-shaped literals are less likely to be altered
- Protect common file names, module names, and path-like literals from accidental translation
- Protect many uppercase technical constants such as kernel-style macro names
- Reduce batch concurrency automatically when the model endpoint returns `429` or other rate-limit signals
- Resume from cached translated segments after an interrupted large-document run
- Auto-detect technical documents and apply lenient validation mode (relaxed residual language threshold, flexible placeholder ordering)
- Real-time segment-level progress feedback with dynamic time estimation
- Transparent retry reason logging for better debugging (API rate limiting, placeholder validation failures, residual language detection, etc.)

Practical recommendations for complex documents:

- Start with `batch_size=4` and `parallel_batches=1` or `2` if your endpoint is rate-limited
- For technical documents with heavy terminology, consider setting `validation_mode=lenient` in `.env`
- Keep glossary entries for product names and domain-specific terminology
- Re-run failed large jobs with the same source file and output directory so the checkpoint cache can be reused
- Treat the generated translation as a technical draft and review tables, constants, and code-adjacent prose before release

DITA support currently focuses on `.dita` topic-style files. It extracts translatable XML text nodes, preserves non-translatable code-like regions, and writes the translated output back as `.dita`.

## Runtime Config

Supported config sources:

- `.env`
- `settings.json`
- runtime environment variables

Priority:

1. Runtime environment variables
2. `.env`
3. `settings.json`
4. Code defaults

Recommended setup for end users:

- Use `.env` as the main config file
- Treat `settings.json` as optional advanced config
- Do not commit real API keys or internal URLs into version control

Config file roles:

- `.env.example`: starter template for `.env`
- `settings.example.json`: starter template for `settings.json`
- `glossary.example.json`: starter template for `glossary.json`
- `.env`: recommended place for endpoint, API key, model name, and other runtime-friendly overrides
- `settings.json`: optional advanced JSON config for users who want to manage batch size, retries, timeouts, max token caps, or front matter fields in one file
- `glossary.json`: optional glossary loaded automatically at translation start

How `.env` and `settings.json` work together:

- If the same field is configured in both files, `.env` wins
- Runtime environment variables still override both `.env` and `settings.json`
- A practical rule is: keep secrets and the most frequently changed model settings in `.env`, and keep slower-changing advanced defaults in `settings.json`

How to use `settings.example.json`:

1. Copy `settings.example.json` to `settings.json`
2. Edit only the fields you actually need
3. Use it mainly for advanced tuning such as `batch_size`, `parallel_batches`, `max_retries`, timeouts, `max_tokens`, and `front_matter_translatable_fields`
4. If you also configure the same keys in `.env`, the `.env` values will take precedence at runtime

How to use `glossary.example.json`:

1. Copy `glossary.example.json` to `glossary.json`, or create/edit `glossary.json` from the GUI glossary editor
2. Add items in the form `{ "source": "...", "target": "..." }`
3. Save the file in the same directory that the app uses as its runtime project root
4. Start a translation task; the glossary is loaded automatically

Glossary usage notes:

- Use glossary entries for product names, module names, internal terms, and stable technical wording
- If you want a term to remain unchanged, set the same text for both `source` and `target`
- `glossary.example.json` itself is only a template; the runtime loader reads `glossary.json`

Useful LLM tuning fields:

- `batch_size`: number of segments sent in one request
- `parallel_batches`: number of batch requests allowed to run at the same time
- `max_retries`: retry count for a failed batch before surfacing an error
- `validation_mode`: validation strictness (strict/balanced/lenient) - use `lenient` for technical documents
- `residual_language_threshold`: maximum allowed residual source language words (auto-set by validation_mode)
- `allow_placeholder_reorder`: whether to allow placeholder reordering (auto-set by validation_mode)
- `min_batch_split_size`: minimum segment count when splitting failed batches (auto-set by validation_mode)

UI status notes:

- Startup only validates whether key config fields are present; it does not send a network request yet
- Real connectivity is checked when translation starts
- Translation progress now reports both `正在处理第 x/N 批` and `已完成批次 x/N`

## Main User Docs

- `使用指南.md`: Chinese end-user guide
- `PACKAGING.md`: Windows packaging notes
- `PACKAGING_MACOS.md`: macOS packaging notes

Repository layout:

- Source project root: `source/`
- Generated packages: `../releases/`
- `CHANGELOG.md`: release history

## Versioning

- Runtime version source: `doc_translation_tool.__version__`
- Packaging metadata reads the version dynamically from code
- Release notes are recorded in `CHANGELOG.md`
- Unreleased local improvements should be recorded under the `Unreleased` section before the next tag is created

When preparing a new release:

1. Update `doc_translation_tool/__init__.py`
2. Append release notes to `CHANGELOG.md`
3. Rebuild packages:
   - Windows: Run `scripts\build_windows.ps1` in PowerShell
   - macOS: Run `bash scripts/build_macos.sh`
