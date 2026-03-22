from pathlib import Path

from doc_translation_tool import __version__
from doc_translation_tool.config.settings import load_app_settings, summarize_settings


def test_load_app_settings_uses_defaults_when_no_files(tmp_path: Path) -> None:
    settings = load_app_settings(tmp_path)

    assert settings.project_root == str(tmp_path)
    assert settings.llm.provider == "openai_compatible"
    assert settings.llm.api_format == "openai"
    assert settings.llm.anthropic_version == "2023-06-01"
    assert settings.llm.base_url == ""
    assert settings.llm.api_key == ""
    assert settings.llm.model == ""
    assert settings.llm.timeout == 60
    assert settings.llm.parallel_batches == 2
    assert settings.front_matter_translatable_fields == ("title", "subtitle", "desc")


def test_load_app_settings_reads_settings_json(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        (
            "{\n"
            '  "llm": {\n'
            '    "provider": "openai_compatible",\n'
            '    "api_format": "openai",\n'
            '    "base_url": "https://json.example/v1",\n'
            '    "model": "json-model",\n'
            '    "timeout": 45,\n'
            '    "batch_size": 12,\n'
            '    "parallel_batches": 4\n'
            "  },\n"
            '  "markdown": {\n'
            '    "front_matter_translatable_fields": ["title", "author"]\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    settings = load_app_settings(tmp_path)

    assert settings.llm.base_url == "https://json.example/v1"
    assert settings.llm.model == "json-model"
    assert settings.llm.timeout == 45
    assert settings.llm.batch_size == 12
    assert settings.llm.parallel_batches == 4
    assert settings.front_matter_translatable_fields == ("title", "author")


def test_load_app_settings_env_file_overrides_settings_json(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(
        (
            "{\n"
            '  "llm": {\n'
            '    "base_url": "https://json.example/v1",\n'
            '    "model": "json-model",\n'
            '    "timeout": 45\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        (
            "DOC_TRANS_BASE_URL=https://env.example/v1\n"
            "DOC_TRANS_MODEL=env-model\n"
            "DOC_TRANS_TIMEOUT=90\n"
            "DOC_TRANS_API_KEY=env-secret\n"
        ),
        encoding="utf-8",
    )

    settings = load_app_settings(tmp_path)

    assert settings.llm.base_url == "https://env.example/v1"
    assert settings.llm.model == "env-model"
    assert settings.llm.timeout == 90
    assert settings.llm.api_key == "env-secret"


def test_load_app_settings_explicit_env_overrides_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        (
            "DOC_TRANS_MODEL=dotenv-model\n"
            "DOC_TRANS_BATCH_SIZE=6\n"
            "DOC_TRANS_PARALLEL_BATCHES=3\n"
        ),
        encoding="utf-8",
    )

    settings = load_app_settings(
        tmp_path,
        env_overrides={
            "DOC_TRANS_MODEL": "runtime-model",
            "DOC_TRANS_BATCH_SIZE": "10",
            "DOC_TRANS_PARALLEL_BATCHES": "5",
        },
    )

    assert settings.llm.model == "runtime-model"
    assert settings.llm.batch_size == 10
    assert settings.llm.parallel_batches == 5


def test_load_app_settings_reads_anthropic_env_fields(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        (
            "DOC_TRANS_PROVIDER=openai_compatible\n"
            "DOC_TRANS_API_FORMAT=anthropic\n"
            "DOC_TRANS_ANTHROPIC_VERSION=2023-06-01\n"
            "DOC_TRANS_BASE_URL=https://anthropic.example/v1\n"
            "DOC_TRANS_API_KEY=env-secret\n"
            "DOC_TRANS_MODEL=claude-compatible\n"
        ),
        encoding="utf-8",
    )

    settings = load_app_settings(tmp_path)

    assert settings.llm.provider == "openai_compatible"
    assert settings.llm.api_format == "anthropic"
    assert settings.llm.anthropic_version == "2023-06-01"
    assert settings.llm.base_url == "https://anthropic.example/v1"
    assert settings.llm.model == "claude-compatible"


def test_load_app_settings_front_matter_fields_env_override(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(
        (
            "{\n"
            '  "markdown": {\n'
            '    "front_matter_translatable_fields": ["title"]\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "DOC_TRANS_FRONT_MATTER_FIELDS=title,subtitle\n",
        encoding="utf-8",
    )

    settings = load_app_settings(
        tmp_path,
        env_overrides={"DOC_TRANS_FRONT_MATTER_FIELDS": "author,desc"},
    )

    assert settings.front_matter_translatable_fields == ("author", "desc")


def test_summarize_settings_hides_api_key(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        (
            "DOC_TRANS_BASE_URL=https://env.example/v1\n"
            "DOC_TRANS_API_KEY=top-secret\n"
            "DOC_TRANS_MODEL=env-model\n"
        ),
        encoding="utf-8",
    )

    summary = summarize_settings(load_app_settings(tmp_path))

    assert "top-secret" not in summary
    assert "API key: configured" in summary
    assert "Front matter fields: title, subtitle, desc" in summary


def test_pyproject_dynamic_version_matches_package_version() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    assert 'dynamic = ["version"]' in content
    assert 'version = { attr = "doc_translation_tool.__version__" }' in content
    assert __version__ == "0.4.3"
