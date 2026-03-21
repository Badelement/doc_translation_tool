# Changelog

All notable changes to this project are recorded in this file.

## Unreleased

Improved:

- Upgraded the Windows packaging workflow actions to Node 24 compatible versions to address GitHub Actions deprecation warnings during release builds

Docs:

- Recorded the CI workflow compatibility maintenance in `开发问题记录.md`

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
