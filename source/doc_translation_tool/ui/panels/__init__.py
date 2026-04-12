"""UI panel components for the main window."""

from doc_translation_tool.ui.panels.batch_translation_panel import BatchTranslationPanel
from doc_translation_tool.ui.panels.status_components import ActionBar, LogGroup, ProgressGroup
from doc_translation_tool.ui.panels.translation_panel import TranslationPanel

__all__ = [
    "TranslationPanel",
    "BatchTranslationPanel",
    "ProgressGroup",
    "LogGroup",
    "ActionBar",
]
