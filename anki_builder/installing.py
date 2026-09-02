from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys

from .models import Project


DEFAULT_ANKI_PYTHON = (
    Path.home()
    / "Library"
    / "Application Support"
    / "AnkiProgramFiles"
    / ".venv"
    / "bin"
    / "python"
)


def install_project(
    project: Project,
    build_report: dict,
    output_dir: Path,
    collection_path: Path,
    anki_python: Path = DEFAULT_ANKI_PYTHON,
) -> dict:
    if not anki_python.is_file():
        raise FileNotFoundError(f"Anki Python runtime not found: {anki_python}")
    payload = {
        "project_id": project.project_id,
        "collection_path": str(collection_path),
        "output_dir": str(output_dir),
        "packages": build_report["packages"],
        "desired_cards": build_report["desired_cards"],
        "decks": [
            {"key": deck.key, "path": deck.path, "expected_count": deck.expected_count}
            for deck in project.decks
        ],
        "installation": project.installation,
    }
    payload_path = output_dir / "install-payload.json"
    payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    environment = dict(os.environ)
    package_root = str(Path(__file__).resolve().parent.parent)
    environment["PYTHONPATH"] = package_root + os.pathsep + environment.get("PYTHONPATH", "")
    command = [str(anki_python), "-m", "anki_builder.install_worker", str(payload_path)]
    completed = subprocess.run(command, text=True, capture_output=True, env=environment)
    if completed.returncode:
        raise RuntimeError(
            "Anki installation failed; install-report.json records rollback status. "
            "If the collection was locked, close Anki cleanly and retry.\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    report_path = output_dir / "install-report.json"
    if not report_path.is_file():
        raise RuntimeError("Installer completed without writing install-report.json")
    return json.loads(report_path.read_text(encoding="utf-8"))
