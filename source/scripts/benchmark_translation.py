from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from doc_translation_tool.config import AppSettings, LLMSettings, load_app_settings
from doc_translation_tool.llm import BaseLLMClient, create_llm_client
from doc_translation_tool.models import BatchTranslationTask, TranslationTask
from doc_translation_tool.services import (
    BatchTranslationError,
    BatchTranslationService,
    DocumentTranslationPipeline,
)


@dataclass(slots=True)
class BenchmarkMetrics:
    mode: str
    source: str
    output_dir: str
    direction: str
    provider: str
    recursive: bool = False
    files_total: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    total_elapsed_seconds: float = 0.0
    avg_file_seconds: float = 0.0
    total_segments: int = 0
    total_batches: int = 0
    total_retries: int = 0
    total_rate_limit_backoff: int = 0
    total_cached_segments: int = 0
    client_creations: int = 0
    connection_checks: int = 0
    translate_batch_calls: int = 0
    translated_items_sent: int = 0
    mock_delay_ms: int = 0


class CountingClient(BaseLLMClient):
    """Wrapper that counts model interactions for benchmark reporting."""

    def __init__(
        self,
        inner: BaseLLMClient,
        metrics: BenchmarkMetrics,
        *,
        mock_delay_ms: int = 0,
    ) -> None:
        super().__init__(inner.settings)
        self._inner = inner
        self._metrics = metrics
        self._mock_delay_ms = max(0, mock_delay_ms)

    def check_connection(self) -> str:
        self._metrics.connection_checks += 1
        self._sleep_if_needed()
        return self._inner.check_connection()

    def translate_batch(self, items, direction: str, glossary=None):
        self._metrics.translate_batch_calls += 1
        self._metrics.translated_items_sent += len(items)
        self._sleep_if_needed()
        return self._inner.translate_batch(
            items,
            direction=direction,
            glossary=glossary,
        )

    def close(self) -> None:
        self._inner.close()

    def _sleep_if_needed(self) -> None:
        if self._mock_delay_ms > 0:
            time.sleep(self._mock_delay_ms / 1000)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a lightweight benchmark for single-file or batch translation.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source file or source directory to benchmark.",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / ".tmp" / "benchmark_output"),
        help="Output directory for generated translations.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "single", "batch"),
        default="auto",
        help="Benchmark mode. 'auto' infers from the source path.",
    )
    parser.add_argument(
        "--direction",
        choices=("zh_to_en", "en_to_zh"),
        default="zh_to_en",
        help="Translation direction.",
    )
    parser.add_argument(
        "--provider",
        choices=("mock", "project"),
        default="mock",
        help="Use a deterministic mock provider or the current project config.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size override when --provider mock is used.",
    )
    parser.add_argument(
        "--parallel-batches",
        type=int,
        default=2,
        help="Parallel batch override when --provider mock is used.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Retry override when --provider mock is used.",
    )
    parser.add_argument(
        "--mock-delay-ms",
        type=int,
        default=0,
        help="Optional artificial delay applied to each mock connection check and batch request.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print metrics as JSON only.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories when --mode batch is used.",
    )
    return parser.parse_args()


def _resolve_mode(source_path: Path, requested_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    return "batch" if source_path.is_dir() else "single"


def _build_mock_settings(args: argparse.Namespace) -> AppSettings:
    return AppSettings(
        project_root=str(PROJECT_ROOT),
        llm=LLMSettings(
            provider="mock",
            api_format="openai",
            base_url="mock://benchmark",
            api_key="mock-key",
            model="mock-model",
            batch_size=args.batch_size,
            parallel_batches=args.parallel_batches,
            max_retries=args.max_retries,
        ),
    )


def _build_settings_loader(args: argparse.Namespace):
    if args.provider == "project":
        return lambda _root: load_app_settings(PROJECT_ROOT)

    settings = _build_mock_settings(args)
    return lambda _root: settings


def _build_counting_client_factory(
    metrics: BenchmarkMetrics,
    args: argparse.Namespace,
):
    def factory(settings: LLMSettings):
        metrics.client_creations += 1
        inner = create_llm_client(settings)
        return CountingClient(
            inner,
            metrics,
            mock_delay_ms=args.mock_delay_ms if args.provider == "mock" else 0,
        )

    return factory


def _build_pipeline_factory(
    metrics: BenchmarkMetrics,
    args: argparse.Namespace,
):
    settings_loader = _build_settings_loader(args)
    client_factory = _build_counting_client_factory(metrics, args)

    def factory() -> DocumentTranslationPipeline:
        return DocumentTranslationPipeline(
            project_root=PROJECT_ROOT,
            settings_loader=settings_loader,
            client_factory=client_factory,
        )

    return factory


def _run_single_benchmark(
    metrics: BenchmarkMetrics,
    source_path: Path,
    output_dir: Path,
    args: argparse.Namespace,
) -> None:
    pipeline = _build_pipeline_factory(metrics, args)()
    result = pipeline.execute(
        TranslationTask(
            source_path=str(source_path),
            output_dir=str(output_dir),
            direction=args.direction,
        )
    )
    metrics.files_total = 1
    metrics.files_succeeded = 1
    metrics.total_elapsed_seconds = result.overall_elapsed_seconds
    metrics.avg_file_seconds = result.overall_elapsed_seconds
    metrics.total_segments = result.total_segments
    metrics.total_batches = result.total_batches
    metrics.total_retries = result.retry_attempts
    metrics.total_rate_limit_backoff = result.rate_limit_backoff_count
    metrics.total_cached_segments = result.reused_cached_segments


def _run_batch_benchmark(
    metrics: BenchmarkMetrics,
    source_dir: Path,
    output_dir: Path,
    args: argparse.Namespace,
) -> None:
    service = BatchTranslationService(
        pipeline_factory=_build_pipeline_factory(metrics, args),
    )
    result = service.execute(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction=args.direction,
            recursive=args.recursive,
        )
    )
    metrics.files_total = result.total_files
    metrics.files_succeeded = result.successful_files
    metrics.files_failed = result.failed_files
    metrics.files_skipped = result.skipped_files
    metrics.total_elapsed_seconds = result.overall_elapsed_seconds
    metrics.avg_file_seconds = (
        result.overall_elapsed_seconds / result.total_files
        if result.total_files > 0
        else 0.0
    )
    metrics.total_segments = sum(item.total_segments for item in result.successful_results)
    metrics.total_batches = sum(item.total_batches for item in result.successful_results)
    metrics.total_retries = sum(item.retry_attempts for item in result.successful_results)
    metrics.total_rate_limit_backoff = sum(
        item.rate_limit_backoff_count for item in result.successful_results
    )
    metrics.total_cached_segments = sum(
        item.reused_cached_segments for item in result.successful_results
    )


def _format_human_summary(metrics: BenchmarkMetrics) -> str:
    return "\n".join(
        [
            f"mode={metrics.mode}",
            f"source={metrics.source}",
            f"output_dir={metrics.output_dir}",
            f"direction={metrics.direction}",
            f"provider={metrics.provider}",
            f"recursive={metrics.recursive}",
            f"files_total={metrics.files_total}",
            f"files_succeeded={metrics.files_succeeded}",
            f"files_failed={metrics.files_failed}",
            f"files_skipped={metrics.files_skipped}",
            f"elapsed={metrics.total_elapsed_seconds:.3f}s",
            f"avg_file={metrics.avg_file_seconds:.3f}s",
            f"segments={metrics.total_segments}",
            f"batches={metrics.total_batches}",
            f"retries={metrics.total_retries}",
            f"rate_limit_backoff={metrics.total_rate_limit_backoff}",
            f"cached_segments={metrics.total_cached_segments}",
            f"client_creations={metrics.client_creations}",
            f"connection_checks={metrics.connection_checks}",
            f"translate_batch_calls={metrics.translate_batch_calls}",
            f"translated_items_sent={metrics.translated_items_sent}",
            f"mock_delay_ms={metrics.mock_delay_ms}",
        ]
    )


def main() -> int:
    args = _parse_args()
    source_path = Path(args.source).expanduser()
    output_dir = Path(args.output).expanduser()

    if not source_path.exists():
        print(f"benchmark failed: source path does not exist: {source_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    mode = _resolve_mode(source_path, args.mode)
    metrics = BenchmarkMetrics(
        mode=mode,
        source=str(source_path),
        output_dir=str(output_dir),
        direction=args.direction,
        provider=args.provider,
        recursive=args.recursive,
        mock_delay_ms=args.mock_delay_ms,
    )

    try:
        if mode == "single":
            _run_single_benchmark(metrics, source_path, output_dir, args)
        else:
            _run_batch_benchmark(metrics, source_path, output_dir, args)
    except BatchTranslationError as exc:
        print(f"batch benchmark failed: {exc.stage}: {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(metrics), ensure_ascii=False, indent=2))
        return 0

    print(_format_human_summary(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
