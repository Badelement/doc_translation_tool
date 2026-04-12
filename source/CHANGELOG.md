# Changelog

All notable changes to this project are recorded in this file.

## Unreleased

## v0.4.7 - 2026-04-13

Documentation:

- Added professional README with badges, features showcase, and application screenshots
- Added MIT LICENSE file
- Added CONTRIBUTING.md with development guidelines and code style requirements
- Added GitHub templates for pull requests, bug reports, and feature requests
- Added CI/CD workflow for automated testing across multiple platforms
- Added comprehensive CONFIGURATION.md guide covering all settings and use cases
- Added 4 application screenshots demonstrating key features
- Updated .gitignore to exclude sensitive configuration files

Added:

- Added macOS support with dedicated build script (`scripts/build_macos.sh`) and packaging documentation (`PACKAGING_MACOS.md`)
- Added real-time segment-level progress feedback showing "已翻译 X/Y 段，预计剩余 Xs" during translation
- Added dynamic time estimation based on recent batch translation speeds to predict remaining translation time
- Added retry reason classification and transparent logging for better debugging (API rate limiting, placeholder validation failures, residual language detection, network errors, etc.)
- Added detailed logging for fallback strategies (single-segment placeholder rescue, residual language rescue, batch splitting)

Improved:

- Reverted the GUI main flow from the experimental multi-file picker back to `单文件 / 目录批量`, while keeping service-layer directory batch support for benchmark and compatibility use cases
- Enhanced directory batch runs to auto-scan supported files, detect translation direction per file, use the selected direction only as a fallback for uncertain files, and skip likely previously generated `_en` / `_zh` outputs when the original source is present
- Added a batch preflight summary dialog and persisted the batch execution summary into the task log so users can review detected Chinese / English / uncertain counts after the run starts
- Added timestamps to GUI task-summary lines and a `查看详细日志` button that opens the current task log inside a read-only dialog
- Optimized placeholder replacement algorithm to avoid partial replacement conflicts by sorting tokens by length
- Pre-compiled frequently used regular expressions at module level for better performance
- Optimized string operations in table row splitting and sentence segmentation using string slicing instead of character list concatenation
- Reduced comment pattern duplication from 146 lines to 32 lines by sharing regex instances
- Added configurable validation modes (strict/balanced/lenient) with automatic document type detection for technical documents
- Relaxed residual language detection threshold from 3 to 8 words for technical documents with mixed terminology
- Improved placeholder order validation to use set comparison instead of strict ordering, with directional keyword detection for special cases
- Increased minimum batch split size from 1 to 3 to prevent excessive fragmentation and quality degradation

Refactored:

- **Phase 1**: Extracted `PipelineLogger` utility class to eliminate repetitive log callback patterns across pipeline, batch translation, and task service modules (reduced ~12 lines of boilerplate)
- **Phase 2**: Decomposed 1468-line `MainWindow` God Class into 5 independent UI components:
  - `TranslationPanel` (224 lines) - single file translation interface
  - `BatchTranslationPanel` (227 lines) - directory batch translation interface  
  - `ProgressGroup` - progress bar and status display
  - `LogGroup` - log output viewer
  - `ActionBar` - operation buttons (start, reset, config, glossary, task log)
  - Reduced MainWindow from 1468 to 1364 lines (-104 lines)
  - Maintained backward compatibility through property accessors for all 264 unit tests
  - Improved separation of concerns and testability through Signal/Slot decoupling

Fixed:

- Replaced all production assert statements with explicit exception raising for better error handling
- Added thread lock protection for concurrent writes to shared translation result dictionary
- Fixed resource leak in LLM client initialization failure scenarios
- Added input validation and range checking for configuration parameters (timeout: 1-600s, batch_size: 1-100, parallel_batches: 1-20, max_retries: 0-10, temperature: 0.0-2.0, max_tokens: 1-1000000)
- Added warning logs for silent DITA XML parsing errors

## v0.4.6 - 2026-04-07

Fixed:

- Added a single-segment residual-language fallback path so `en_to_zh` / `zh_to_en` jobs can retry placeholder-heavy mixed technical sentences by smaller line-or-sentence chunks instead of failing the whole batch immediately
- Reduced false hard-failures on English technical Markdown documents such as repository guidance files when a single segment keeps a few stable English technical terms after the normal retry budget is exhausted

## v0.4.5 - 2026-04-07

Improved:

- Hardened checkpoint resume handling so corrupted cache files are ignored and cleaned automatically instead of crashing the run before translation starts
- Preserved in-tree DITA XML comments, processing instructions, and namespace prefixes more reliably during document rebuilds
- Cleaned project-side transient artifacts before packaging and rebuilt the Windows release bundle from the refreshed workspace

Fixed:

- Wrapped DITA/XML parse failures as a dedicated `parse_document` pipeline stage so the GUI can surface a specific, actionable error instead of an unknown failure
- Added a GUI troubleshooting hint for document-parse failures, especially for malformed DITA/XML input

## v0.4.4 - 2026-03-25

Added:

- Added single-file `.dita` translation support through the main desktop flow alongside existing Markdown support
- Added a DITA document handler, document-type registry, and `.dita` fixtures / regression coverage for topic-style XML content
- Added a registrable document-format layer so future file types can be plugged in through centralized type and handler registration
- Added document-type-aware language detection hooks so handlers can provide cleaner text samples for auto direction switching and mismatch warnings
- Added a dedicated GUI glossary editor so users can add, delete, and save glossary terms into `glossary.json` without manually editing JSON
- Added a glossary-editor shortcut for terms that should remain unchanged by copying the source term into the target column

Improved:

- Updated GUI and pipeline wording to report generic document parsing instead of Markdown-only parsing when multi-format support is active
- Updated repository docs and the Chinese user guide to describe current Markdown plus DITA support and extension-preserving output behavior
- Improved DITA language detection to ignore non-translatable code-like regions such as `codeblock` and `screen` when estimating source language
- Added a dedicated GUI model-configuration dialog so users can edit provider, API format, base URL, API key, model name, and Anthropic version without manually opening `.env`
- Added `.env` write-back support for the key single-endpoint AI service fields so saved GUI configuration is reused by subsequent translation runs
- Added an in-dialog connectivity test flow and API-key show/hide toggle to reduce configuration mistakes before starting a translation
- Improved connectivity-test feedback so common failures such as auth errors, endpoint mismatches, rate limits, timeouts, TLS issues, and unreachable hosts are classified with clearer troubleshooting guidance
- Changed reset behavior so it clears task state, progress, and logs while keeping the selected source file, output directory, and translation direction
- Allowed repeat translation runs to overwrite existing generated output files while still protecting the source file from being overwritten

Docs:

- Clarified how `.env`, `settings.json`, `settings.example.json`, `glossary.example.json`, and `glossary.json` relate to each other and which files are templates versus runtime inputs
- Removed a misleading `glossary.path` example from `settings.example.json` so the template matches the current runtime behavior

## v0.4.3 - 2026-03-23

Improved:

- Added a single-segment placeholder-order rescue path: when a lone segment fails validation because protected placeholders were reordered, the tool retries that segment as smaller placeholder-bound chunks before giving up
- Added translation summary counters for cached-segment reuse, `429` concurrency backoff events, split-batch fallback events, and single-segment placeholder rescue events to improve large-document observability

Fixed:

- Reduced hard failures on complex Markdown documents where a single placeholder-heavy segment would previously fail the whole run after repeated placeholder-order validation errors

Docs:

- Simplified the Chinese user guide and Chinese repository intro so first-time users can get started with fewer configuration mistakes
- Added clearer Anthropic-compatible configuration examples and highlighted that `DOC_TRANS_BASE_URL` should usually be the service root rather than a manually appended `/messages` endpoint

## v0.4.2 - 2026-03-22

Improved:

- Refreshed the Windows packaging automation to stay compatible with the current local release toolchain
- Hardened Markdown segmentation for complex technical tables by splitting overlong table rows more safely, especially when cells contain many `<br>`-separated technical literals
- Protected embedded HTML/XML-style tags inside translatable text so configuration snippets and tag-shaped literals are less likely to be altered by the model
- Protected common technical file names and path literals such as `board.dts`, `build.sh`, `.ko` modules, and structured config paths from accidental translation
- Added adaptive parallel-batch fallback for `429` / rate-limit failures so unfinished batches can continue at a lower concurrency instead of failing the whole run immediately
- Added lightweight translation checkpoint caching so large-document runs can resume from already translated segments after a failure
- Preserved successful results from completed parallel batches even when another batch in the same completion wave fails, so checkpoint callbacks can still save finished segments before the run aborts
- Added `scripts/run_tests.ps1` so local pytest runs use repository-scoped temp and cache directories under `.tmp/pytest` instead of scattering new cache artifacts in the repo root

Fixed:

- Eliminated over-limit translation segments produced by certain long table rows in complex Markdown technical documents
- Reduced the chance of malformed or semantically broken output caused by the model translating technical tags, file names, or path literals that should remain stable
- Reduced wasted work when large translation tasks fail late in the run by reusing previously translated segments on the next attempt
- Reduced lost progress during mixed parallel outcomes where one batch succeeds but another fails in the same completion wave

Docs:

- Updated release version references in the repository README files and user guide
- Recorded the packaging automation compatibility maintenance in the development issue log
- Recorded the recent complex-document reliability work in the development issue log

## v0.4.1 - 2026-03-21

Fixed:

- Corrected parallel batch progress reporting so the GUI no longer jumps to `正在处理第最后一批/总批次` as soon as translation starts
- Changed parallel batch scheduling to emit start-state updates only for batches that have actually entered the active worker window
- Adjusted translation-stage progress calculation so the progress bar moves more visibly with completed batches, especially on large documents with many batches

Docs:

- Updated release version references in the repository README files and Chinese user guide
- Recorded the progress-state troubleshooting and fix in `开发问题记录.md`

## v0.4.0 - 2026-03-21

Improved:

- Auto-switch the translation direction to `en_to_zh` or `zh_to_en` when the selected Markdown file is confidently detected as English or Chinese
- Refined translation-stage progress updates so the GUI reports both `正在处理第 x/N 批` and `已完成批次 x/N` instead of staying on a vague early-stage waiting message
- Added startup-side model configuration hinting in the GUI so users can see `配置不完整` / `配置已加载，待检查连通性` before clicking the translate button
- Clarified the bottom-left GUI status wording to distinguish configuration loading, connectivity checking, successful connectivity, configuration errors, and connectivity failures

Docs:

- Updated `README.md` and `使用指南.md` to document the new startup model-status hints, auto direction switching, and batch-based progress behavior
- Recorded the latest local optimization notes in `开发问题记录.md`

## v0.3.3 - 2026-03-21

Fixed:

- Corrected the placeholder-format normalization test so the Windows release workflow no longer fails on an invalid multi-item assumption when the segmented table input produces a single translation segment
- Reissued the release after the previous `v0.3.2` tag was created before the final test fix and did not produce a successful Windows package

## v0.3.2 - 2026-03-21

Fixed:

- Reissued the Windows package from the correct release commit after the previous `v0.3.1` tag pointed to an older package-build commit and produced a `0.3.0` app bundle by mistake

Improved:

- Added explicit release notes clarifying that the placeholder-normalization and elapsed-time UI improvements are the intended changes included in the corrected package

## v0.3.1 - 2026-03-21

Improved:

- Normalized loose and escaped placeholder token variants before validation so LLM output like `@@ protect-0 @@` or escaped `@` sequences no longer fail placeholder checks unnecessarily
- Promoted the total translation elapsed time into the pipeline result so the GUI can show a stable completion message with final duration
- Kept the completion status context in the status bar after the worker finishes, instead of immediately replacing it with a generic idle message

Fixed:

- Reduced false-positive placeholder validation failures caused by non-canonical placeholder formatting from the model

## v0.3.0 - 2026-03-20

Improved:

- Added residual-English validation for `en_to_zh` translations to catch partial source-language output earlier
- Strengthened the translation prompt so responses must fully stay in the target language and preserve structure
- Added timestamped GUI logs, elapsed-time display, batch timing logs, and retry-count visibility during runs
- Improved translation-stage progress updates with clearer transition states and completion-based batch messaging
- Reduced large-document segment explosion by packing compatible table lines into fewer translation segments

Fixed:

- Pipeline cleanup now preserves `model_config` errors raised before client creation instead of masking them during shutdown
- Pipeline now closes the LLM client even when glossary loading fails before the translation stage begins

## v0.2.0 - 2026-03-20

Added:

- Reset button in the desktop GUI so the next translation run can start from a clean state
- Anthropic-compatible Messages API support via `DOC_TRANS_API_FORMAT=anthropic`
- Configurable batch-level parallel translation via `parallel_batches`

Improved:

- README and example config now document the batch parallelism setting
- Runtime configuration now supports `DOC_TRANS_PARALLEL_BATCHES` and matching `settings.json` field

Fixed:

- Language-direction mismatch warning now triggers on the initial file load instead of only after toggling translation direction
- Batch translation now keeps retry, split-fallback, and final rebuild behavior while running batches in parallel

## v0.1.0 - 2026-03-20

Initial internal release.

Added:

- PySide6 desktop GUI for single-file Markdown translation
- Input validation, path selection, drag-and-drop and language-direction warning
- `.env` and `settings.json` based configuration loading
- OpenAI-compatible LLM client integration
- Offline `mock` provider for end-to-end flow verification without external API quota
- Markdown parsing, protection, segmentation and rebuild pipeline
- Glossary loading and front matter field control
- Table structure protection and placeholder validation
- Retry logging, batch failure context and automatic split fallback on structure errors
- Windows one-folder packaging, usage guide and troubleshooting docs

Improved:

- Packaged app now reads runtime config from the exe directory
- 429 rate-limit errors now surface clearer suggestions in the GUI
- Packaging script now copies the real `.env` first and reliably includes the Chinese user guide
- Window title and app summary now display the runtime version

Verified:

- Full automated test suite passing
- Packaged GUI flow validated with both real API and offline mock mode
