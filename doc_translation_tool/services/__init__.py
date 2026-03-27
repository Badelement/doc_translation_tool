"""Application services package."""

from doc_translation_tool.services.glossary_loader import load_glossary, save_glossary
from doc_translation_tool.services.lang_detect import (
    LanguageDetectionResult,
    detect_language_for_document,
    detect_language_from_file,
    detect_language_from_text,
    direction_display_name,
    language_matches_direction,
)
from doc_translation_tool.services.output_writer import (
    DocumentOutputWriter,
    MarkdownOutputWriter,
    OutputWriteError,
    OutputWriteResult,
)
from doc_translation_tool.services.pipeline import (
    DocumentTranslationPipeline,
    TranslationPipelineError,
    TranslationPipelineResult,
)
from doc_translation_tool.services.task_service import (
    BatchTranslationResult,
    TranslationTaskService,
)
from doc_translation_tool.services.validator import (
    InputValidationResult,
    validate_translation_inputs,
)

__all__ = [
    "BatchTranslationResult",
    "DocumentOutputWriter",
    "InputValidationResult",
    "LanguageDetectionResult",
    "MarkdownOutputWriter",
    "OutputWriteError",
    "OutputWriteResult",
    "DocumentTranslationPipeline",
    "TranslationTaskService",
    "TranslationPipelineError",
    "TranslationPipelineResult",
    "load_glossary",
    "save_glossary",
    "detect_language_for_document",
    "detect_language_from_file",
    "detect_language_from_text",
    "direction_display_name",
    "language_matches_direction",
    "validate_translation_inputs",
]
