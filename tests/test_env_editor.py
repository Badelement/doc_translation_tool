from pathlib import Path

from doc_translation_tool.config import load_env_file_values, save_env_file_values


def test_save_env_file_values_updates_managed_keys_and_preserves_other_lines(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# existing comment",
                "DOC_TRANS_BASE_URL=https://old.example/v1",
                "UNRELATED_SETTING=keep-me",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    save_env_file_values(
        tmp_path,
        {
            "DOC_TRANS_BASE_URL": "https://new.example/v1",
            "DOC_TRANS_API_KEY": "new-secret",
            "DOC_TRANS_MODEL": "new-model",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "# existing comment" in content
    assert "DOC_TRANS_BASE_URL=https://new.example/v1" in content
    assert "DOC_TRANS_API_KEY=new-secret" in content
    assert "DOC_TRANS_MODEL=new-model" in content
    assert "UNRELATED_SETTING=keep-me" in content


def test_load_env_file_values_reads_saved_values(tmp_path: Path) -> None:
    save_env_file_values(
        tmp_path,
        {
            "DOC_TRANS_PROVIDER": "openai_compatible",
            "DOC_TRANS_API_FORMAT": "openai",
            "DOC_TRANS_BASE_URL": "https://env.example/v1",
            "DOC_TRANS_API_KEY": "secret-key",
            "DOC_TRANS_MODEL": "env-model",
        },
    )

    values = load_env_file_values(tmp_path)

    assert values["DOC_TRANS_PROVIDER"] == "openai_compatible"
    assert values["DOC_TRANS_API_FORMAT"] == "openai"
    assert values["DOC_TRANS_BASE_URL"] == "https://env.example/v1"
    assert values["DOC_TRANS_API_KEY"] == "secret-key"
    assert values["DOC_TRANS_MODEL"] == "env-model"


def test_save_env_file_values_persists_advanced_llm_keys(tmp_path: Path) -> None:
    save_env_file_values(
        tmp_path,
        {
            "DOC_TRANS_TIMEOUT": "90",
            "DOC_TRANS_CONNECT_TIMEOUT": "12",
            "DOC_TRANS_READ_TIMEOUT": "120",
            "DOC_TRANS_MAX_RETRIES": "3",
            "DOC_TRANS_BATCH_SIZE": "16",
            "DOC_TRANS_PARALLEL_BATCHES": "4",
            "DOC_TRANS_TEMPERATURE": "0.3",
            "DOC_TRANS_MAX_TOKENS": "4096",
        },
    )

    values = load_env_file_values(tmp_path)

    assert values["DOC_TRANS_TIMEOUT"] == "90"
    assert values["DOC_TRANS_CONNECT_TIMEOUT"] == "12"
    assert values["DOC_TRANS_READ_TIMEOUT"] == "120"
    assert values["DOC_TRANS_MAX_RETRIES"] == "3"
    assert values["DOC_TRANS_BATCH_SIZE"] == "16"
    assert values["DOC_TRANS_PARALLEL_BATCHES"] == "4"
    assert values["DOC_TRANS_TEMPERATURE"] == "0.3"
    assert values["DOC_TRANS_MAX_TOKENS"] == "4096"
