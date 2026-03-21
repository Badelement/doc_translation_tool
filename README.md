# Document Translation Tool

Desktop tool for translating a single Markdown document between Chinese and English while preserving Markdown structure.

Current version: `0.3.3`

## What It Does

- Translate one `.md` file at a time
- Support `zh_to_en` and `en_to_zh`
- Support both OpenAI-compatible and Anthropic-compatible API formats
- Support configurable batch-level parallel translation
- Preserve Markdown structure, protected placeholders, tables and front matter rules
- Write output to a new file instead of overwriting the source file

## Quick Start

For packaged Windows use:

1. Extract the full `DocTranslationTool-win64.zip`
2. Open the `dist\DocTranslationTool\` folder
3. Edit `.env` in the same folder as `DocTranslationTool.exe`
4. Fill in your own `DOC_TRANS_BASE_URL`, `DOC_TRANS_API_KEY`, and `DOC_TRANS_MODEL`
5. Launch `DocTranslationTool.exe`

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

## Main User Docs

- `使用指南.md`: end-user guide
- `GitHub使用指南.md`: GitHub and release workflow guide for this project
- `PACKAGING.md`: release packaging notes
- `CHANGELOG.md`: release history

## Versioning

- Runtime version source: `doc_translation_tool.__version__`
- Packaging metadata reads the version dynamically from code
- Release notes are recorded in `CHANGELOG.md`

When preparing a new release:

1. Update `doc_translation_tool/__init__.py`
2. Append release notes to `CHANGELOG.md`
3. Rebuild the Windows package
