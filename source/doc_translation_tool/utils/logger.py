"""Pipeline logging utilities to reduce code duplication."""

from __future__ import annotations

from typing import Callable


class PipelineLogger:
    """Centralized logger that wraps optional callback functions."""

    def __init__(self, callback: Callable[[str], None] | None = None) -> None:
        self._callback = callback

    def log(self, message: str) -> None:
        """Log a message if callback is available."""
        if self._callback is not None:
            self._callback(message)

    def stage(self, stage_name: str, message: str) -> None:
        """Log a stage-prefixed message."""
        self.log(f"[{stage_name}] {message}")

    def file(self, message: str) -> None:
        """Log a file operation message."""
        self.stage("文件", message)

    def config(self, message: str) -> None:
        """Log a configuration message."""
        self.stage("配置", message)

    def model(self, message: str) -> None:
        """Log a model-related message."""
        self.stage("模型", message)

    def parse(self, message: str) -> None:
        """Log a parsing message."""
        self.stage("解析", message)

    def translate(self, message: str) -> None:
        """Log a translation message."""
        self.stage("翻译", message)

    def output(self, message: str) -> None:
        """Log an output message."""
        self.stage("输出", message)

    def complete(self, message: str) -> None:
        """Log a completion message."""
        self.stage("完成", message)

    def batch(self, message: str) -> None:
        """Log a batch operation message."""
        self.stage("批量", message)

    def resume(self, message: str) -> None:
        """Log a checkpoint resume message."""
        self.stage("续跑", message)

    def glossary(self, message: str) -> None:
        """Log a glossary message."""
        self.stage("术语", message)

    def stats(self, message: str) -> None:
        """Log a statistics message."""
        self.stage("stats", message)


class ProgressReporter:
    """Centralized progress reporter that wraps optional callback functions."""

    def __init__(self, callback: Callable[[str, int], None] | None = None) -> None:
        self._callback = callback

    def report(self, message: str, percent: int) -> None:
        """Report progress if callback is available."""
        if self._callback is not None:
            self._callback(message, percent)
