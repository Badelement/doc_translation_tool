# Document Translation Tool

Desktop tool for translating a single Markdown or DITA document between Chinese and English while preserving document structure.

[English](./README.md) | [简体中文](./README.zh-CN.md)

Current release: [v0.4.3](https://github.com/Badelement/doc_translation_tool/releases/tag/v0.4.3)

Latest repository changes after `v0.4.3` are recorded under the `Unreleased` section in [CHANGELOG.md](./CHANGELOG.md).

## Overview

This project focuses on a practical internal workflow:

- Translate one Markdown or DITA document at a time
- Preserve Markdown structure or DITA XML text structure during translation
- Support both Chinese-to-English and English-to-Chinese translation
- Support OpenAI-compatible and Anthropic-compatible API formats
- Support batch parallel translation for better large-document throughput
- Provide clearer GUI feedback for model configuration, connectivity, and batch progress
- Provide in-app dialogs for model settings and glossary editing

## What It Does

- Translate one `.md` or `.dita` file at a time
- Support `zh_to_en` and `en_to_zh`
- Auto-detect common Chinese or English source files and switch the translation direction accordingly
- Support both OpenAI-compatible and Anthropic-compatible API formats
- Support configurable batch-level parallel translation
- Edit model settings from the GUI and save them back into `.env`
- Edit `glossary.json` from the GUI and keep product names / terminology stable more easily
- Show startup model-config status before a translation run begins
- Show translation progress with batch-based running and completion states
- Preserve Markdown structure, protected placeholders, tables and front matter rules
- Preserve DITA XML text nodes while leaving code-like tags and protected literals stable
- Protect embedded HTML/XML-style tags, common technical file names, path literals, and uppercase technical constants
- Resume large translation runs from cached segment results after a failure
- Reduce concurrency automatically after `429` / rate-limit errors during parallel batch translation
- Write output to a new file instead of overwriting the source file

## Quick Start

For packaged Windows use:

1. Extract the full `DocTranslationTool-v<version>-win64.zip`
2. Open the `dist\DocTranslationTool\` folder
3. Launch `DocTranslationTool.exe`
4. Either edit `.env` in the same folder or click `模型配置` in the app
5. Fill in your own `DOC_TRANS_BASE_URL`, `DOC_TRANS_API_KEY`, and `DOC_TRANS_MODEL`
6. Check the bottom-left model status first:
   `配置不完整` means the key fields are missing,
   `配置已加载，待检查连通性` means the config is present and the real API check will happen when translation starts
7. Optionally click `术语配置` to maintain `glossary.json` inside the GUI
8. Select a `.md` or `.dita` file and an output directory
9. The tool may auto-switch the direction when it confidently detects Chinese or English source content
10. Start translation and watch the batch-based progress updates

Most users do not need to edit any other config fields.

For local macOS packaging:

1. Run `bash ./scripts/build_macos.sh`
2. Open `dist-macos/DocTranslationTool-macos-<arch>/`
3. Edit `.env` in the same directory as `DocTranslationTool.app`, or use the in-app `模型配置` dialog after launch
4. Launch `DocTranslationTool.app`

The packaged macOS app reads `.env`, `settings.json`, and `glossary.json` from the directory that contains the `.app` bundle.

## Complex Technical Documents

The tool is now tuned more aggressively for large technical Markdown documents and DITA topics that contain heavy tables, paths, config snippets, and mixed technical literals.

Recent reliability improvements include:

- Split overlong table rows more safely, especially when cells contain many `<br>`-separated values
- Protect embedded HTML/XML-style tags so tag-shaped literals are less likely to be altered
- Protect common file names, module names, and path-like literals from accidental translation
- Protect many uppercase technical constants such as kernel-style macro names
- Reduce batch concurrency automatically when the model endpoint returns `429` or other rate-limit signals
- Resume from cached translated segments after an interrupted large-document run

Practical recommendations for complex documents:

- Start with `batch_size=4` and `parallel_batches=1` or `2` if your endpoint is rate-limited
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
- Use the GUI `模型配置` dialog for everyday edits when you do not want to open config files manually
- Use `glossary.json` or the GUI `术语配置` dialog for terminology pairs that should stay stable
- Do not commit real API keys or internal URLs into version control

Useful LLM tuning fields:

- `batch_size`: number of segments sent in one request
- `parallel_batches`: number of batch requests allowed to run at the same time
- `max_retries`: retry count for a failed batch before surfacing an error
- `temperature`: output creativity / variance control
- `max_tokens`: optional explicit output cap for providers that require one
- `timeout`, `connect_timeout`, `read_timeout`: request-level timeout controls

UI status notes:

- Startup only validates whether key config fields are present; it does not send a network request yet
- Real connectivity is checked when translation starts
- The `模型配置` dialog can also run a connectivity test before you save
- Translation progress now reports both `正在处理第 x/N 批` and `已完成批次 x/N`
- Windows release zip names now include the app version, and the packaged `DocTranslationTool.exe` also carries Windows file version metadata
- Local macOS packages read runtime config from the directory that contains `DocTranslationTool.app`

## Main User Docs

- `README.zh-CN.md`: Chinese project overview for the repository homepage
- `使用指南.md`: end-user guide
- `GitHub使用指南.md`: GitHub and release workflow guide for this project
- `PACKAGING.md`: release packaging notes
- `CHANGELOG.md`: release history

## Versioning

- Runtime version source: `doc_translation_tool.__version__`
- Packaging metadata reads the version dynamically from code
- Release notes are recorded in `CHANGELOG.md`
- Unreleased local improvements should be recorded under the `Unreleased` section before the next tag is created
- The repository may contain newer unreleased improvements even when the latest GitHub Release tag is still `v0.4.3`

When preparing a new release:

1. Update `doc_translation_tool/__init__.py`
2. Append release notes to `CHANGELOG.md`
3. Rebuild the desktop package for the target platform
