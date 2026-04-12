# Configuration Guide

This guide covers advanced configuration options for the Document Translation Tool.

## Configuration Files

The tool supports multiple configuration sources with the following priority:

1. **Environment variables** (highest priority)
2. **`.env` file** (recommended for most users)
3. **`settings.json` file** (optional advanced settings)
4. **Code defaults** (lowest priority)

### `.env` File

The `.env` file is the recommended place for API credentials and frequently changed settings.

```bash
# LLM Provider Configuration
DOC_TRANS_PROVIDER=openai          # openai, anthropic, azure, or custom
DOC_TRANS_BASE_URL=https://api.openai.com/v1
DOC_TRANS_API_KEY=your-api-key-here
DOC_TRANS_MODEL=gpt-4

# Optional: Azure OpenAI specific
# DOC_TRANS_AZURE_API_VERSION=2024-02-15-preview
# DOC_TRANS_AZURE_DEPLOYMENT=your-deployment-name

# Translation Settings
DOC_TRANS_BATCH_SIZE=4             # Segments per request
DOC_TRANS_PARALLEL_BATCHES=2       # Concurrent requests
DOC_TRANS_MAX_RETRIES=3            # Retry attempts

# Validation Mode (strict/balanced/lenient)
DOC_TRANS_VALIDATION_MODE=balanced
```

### `settings.json` File

For advanced users who prefer JSON configuration:

```json
{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4",
  "batch_size": 4,
  "parallel_batches": 2,
  "max_retries": 3,
  "validation_mode": "balanced",
  "request_timeout": 120,
  "max_tokens": 4096,
  "temperature": 0.3
}
```

**Note**: If the same setting exists in both `.env` and `settings.json`, the `.env` value takes precedence.

## LLM Provider Configuration

### OpenAI

```bash
DOC_TRANS_PROVIDER=openai
DOC_TRANS_BASE_URL=https://api.openai.com/v1
DOC_TRANS_API_KEY=sk-...
DOC_TRANS_MODEL=gpt-4
```

### Anthropic

```bash
DOC_TRANS_PROVIDER=anthropic
DOC_TRANS_BASE_URL=https://api.anthropic.com
DOC_TRANS_API_KEY=sk-ant-...
DOC_TRANS_MODEL=claude-3-5-sonnet-20241022
```

### Azure OpenAI

```bash
DOC_TRANS_PROVIDER=azure
DOC_TRANS_BASE_URL=https://your-resource.openai.azure.com
DOC_TRANS_API_KEY=your-azure-key
DOC_TRANS_MODEL=gpt-4
DOC_TRANS_AZURE_API_VERSION=2024-02-15-preview
DOC_TRANS_AZURE_DEPLOYMENT=your-deployment-name
```

### Custom OpenAI-Compatible Endpoints

```bash
DOC_TRANS_PROVIDER=openai
DOC_TRANS_BASE_URL=https://your-custom-endpoint.com/v1
DOC_TRANS_API_KEY=your-key
DOC_TRANS_MODEL=your-model-name
```

## Translation Settings

### Batch Processing

- **`batch_size`**: Number of segments sent in one API request
  - Smaller values (2-4): Better for rate-limited APIs
  - Larger values (8-16): Faster for high-throughput APIs
  - Default: `4`

- **`parallel_batches`**: Number of concurrent API requests
  - Start with `1-2` for rate-limited endpoints
  - Increase to `4-8` for high-throughput endpoints
  - Default: `2`

- **`max_retries`**: Retry attempts for failed requests
  - Default: `3`

### Validation Modes

The tool validates translations to ensure quality. Choose a mode based on your document type:

| Mode | Use Case | Residual Language Threshold | Placeholder Reordering |
|------|----------|----------------------------|----------------------|
| `strict` | Simple documents, high accuracy | 5 words | Not allowed |
| `balanced` | General purpose (default) | 10 words | Not allowed |
| `lenient` | Technical docs with code/tables | 20 words | Allowed |

**Recommendation**: Use `lenient` mode for technical documentation with heavy code blocks, tables, and technical terminology.

```bash
DOC_TRANS_VALIDATION_MODE=lenient
```

### Advanced Validation Settings

For fine-grained control, you can override individual validation parameters:

```bash
# Maximum allowed untranslated words in target language
DOC_TRANS_RESIDUAL_LANGUAGE_THRESHOLD=20

# Allow placeholders to be reordered in translation
DOC_TRANS_ALLOW_PLACEHOLDER_REORDER=true

# Minimum segments when splitting failed batches
DOC_TRANS_MIN_BATCH_SPLIT_SIZE=1
```

## Glossary Configuration

Create a `glossary.json` file to define custom terminology:

```json
[
  {
    "source": "API",
    "target": "API",
    "note": "Keep unchanged"
  },
  {
    "source": "用户界面",
    "target": "User Interface"
  },
  {
    "source": "数据库",
    "target": "Database"
  }
]
```

**Tips**:
- Use glossary for product names, technical terms, and brand names
- Set `source` and `target` to the same value to prevent translation
- The glossary is loaded automatically at translation start
- Edit via GUI: Click "术语配置" button

## Performance Tuning

### For Rate-Limited APIs

```bash
DOC_TRANS_BATCH_SIZE=2
DOC_TRANS_PARALLEL_BATCHES=1
DOC_TRANS_MAX_RETRIES=5
```

### For High-Throughput APIs

```bash
DOC_TRANS_BATCH_SIZE=8
DOC_TRANS_PARALLEL_BATCHES=4
DOC_TRANS_MAX_RETRIES=3
```

### For Large Technical Documents

```bash
DOC_TRANS_BATCH_SIZE=4
DOC_TRANS_PARALLEL_BATCHES=2
DOC_TRANS_VALIDATION_MODE=lenient
DOC_TRANS_MAX_TOKENS=8192
```

## Troubleshooting

### "配置不完整" Status

The tool requires these minimum settings:
- `DOC_TRANS_BASE_URL`
- `DOC_TRANS_API_KEY`
- `DOC_TRANS_MODEL`

Check your `.env` file and ensure all three are set.

### Rate Limiting (429 Errors)

The tool automatically reduces concurrency when rate limits are hit. To prevent this:
- Reduce `parallel_batches` to `1`
- Reduce `batch_size` to `2-4`
- Increase `request_timeout` if needed

### Translation Quality Issues

For technical documents with many untranslated terms:
- Switch to `lenient` validation mode
- Add technical terms to `glossary.json`
- Review and adjust `residual_language_threshold`

### Checkpoint Recovery

If a large translation is interrupted:
1. Keep the same source file and output directory
2. Restart the translation
3. The tool will resume from cached segments

Checkpoint files are stored in `.translation_cache/` in the output directory.

## Front Matter Configuration

For Markdown files with YAML front matter, you can specify which fields should be translated:

```json
{
  "front_matter_translatable_fields": ["title", "description", "summary"]
}
```

By default, most front matter fields are preserved as-is.

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `DOC_TRANS_PROVIDER` | LLM provider (openai/anthropic/azure) | `openai` |
| `DOC_TRANS_BASE_URL` | API endpoint URL | Required |
| `DOC_TRANS_API_KEY` | API authentication key | Required |
| `DOC_TRANS_MODEL` | Model name | Required |
| `DOC_TRANS_BATCH_SIZE` | Segments per request | `4` |
| `DOC_TRANS_PARALLEL_BATCHES` | Concurrent requests | `2` |
| `DOC_TRANS_MAX_RETRIES` | Retry attempts | `3` |
| `DOC_TRANS_VALIDATION_MODE` | Validation strictness | `balanced` |
| `DOC_TRANS_REQUEST_TIMEOUT` | Request timeout (seconds) | `120` |
| `DOC_TRANS_MAX_TOKENS` | Max tokens per request | `4096` |
| `DOC_TRANS_TEMPERATURE` | LLM temperature | `0.3` |

## Mock Mode (Testing)

For testing without API calls:

```bash
DOC_TRANS_PROVIDER=mock
```

This mode simulates translations without making real API requests.
