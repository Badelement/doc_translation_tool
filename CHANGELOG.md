# Changelog

All notable changes to this project are recorded in this file.

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
