from pathlib import Path

from anki_builder.installing import DEFAULT_ANKI_PYTHON


def test_default_anki_runtime_is_user_relative():
    assert DEFAULT_ANKI_PYTHON.name == "python"
    assert ".venv" in str(DEFAULT_ANKI_PYTHON)
    assert Path.home() in DEFAULT_ANKI_PYTHON.parents
