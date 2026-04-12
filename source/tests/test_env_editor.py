from pathlib import Path
import sys

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


def test_save_env_file_values_can_update_hidden_env_file_on_windows(
    tmp_path: Path,
) -> None:
    if sys.platform != "win32":
        return

    env_path = tmp_path / ".env"
    env_path.write_text("DOC_TRANS_MODEL=old-model\n", encoding="utf-8")

    import ctypes

    result = ctypes.windll.kernel32.SetFileAttributesW(str(env_path), 0x02)
    assert result != 0

    save_env_file_values(
        tmp_path,
        {
            "DOC_TRANS_MODEL": "new-model",
        },
    )

    assert "DOC_TRANS_MODEL=new-model" in env_path.read_text(encoding="utf-8")
