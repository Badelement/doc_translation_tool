# Document Translation Tool

Desktop tool for translating a single Markdown document between Chinese and English while preserving Markdown structure.

Current release: `0.4.0`

## What It Does

- Translate one `.md` file at a time
- Support `zh_to_en` and `en_to_zh`
- Auto-detect common Chinese or English source files and switch the translation direction accordingly
- Support both OpenAI-compatible and Anthropic-compatible API formats
- Support configurable batch-level parallel translation
- Show startup model-config status before a translation run begins
- Show translation progress with batch-based running and completion states
- Preserve Markdown structure, protected placeholders, tables and front matter rules
- Write output to a new file instead of overwriting the source file

## Quick Start

For packaged Windows use:

1. Extract the full `DocTranslationTool-win64.zip`
2. Open the `dist\DocTranslationTool\` folder
3. Edit `.env` in the same folder as `DocTranslationTool.exe`
4. Fill in your own `DOC_TRANS_BASE_URL`, `DOC_TRANS_API_KEY`, and `DOC_TRANS_MODEL`
5. Launch `DocTranslationTool.exe`
6. Check the bottom-left model status first:
   `配置不完整` means the key fields are missing,
   `配置已加载，待检查连通性` means the config is present and the real API check will happen when translation starts
7. Select a `.md` file and an output directory
8. The tool may auto-switch the direction when it confidently detects Chinese or English source content
9. Start translation and watch the batch-based progress updates

Most users do not need to edit any other config fields.

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

Useful LLM tuning fields:

- `batch_size`: number of segments sent in one request
- `parallel_batches`: number of batch requests allowed to run at the same time
- `max_retries`: retry count for a failed batch before surfacing an error

UI status notes:

- Startup only validates whether key config fields are present; it does not send a network request yet
- Real connectivity is checked when translation starts
- Translation progress now reports both `正在处理第 x/N 批` and `已完成批次 x/N`

## Main User Docs

- `使用指南.md`: end-user guide
- `GitHub使用指南.md`: GitHub and release workflow guide for this project
- `PACKAGING.md`: release packaging notes
- `CHANGELOG.md`: release history

## Versioning

- Runtime version source: `doc_translation_tool.__version__`
- Packaging metadata reads the version dynamically from code
- Release notes are recorded in `CHANGELOG.md`
- Unreleased local improvements should be recorded under the `Unreleased` section before the next tag is created

When preparing a new release:

1. Update `doc_translation_tool/__init__.py`
2. Append release notes to `CHANGELOG.md`
3. Rebuild the Windows package
