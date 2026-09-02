from __future__ import annotations

from pathlib import Path

import yaml

from anki_builder.models import load_project
from anki_builder.reviewing import (
    project_fingerprint,
    record_approval,
    render_review,
    require_current_approval,
)


def make_review_project(tmp_path: Path):
    root = tmp_path / "repository"
    project_dir = root / "projects" / "review-test"
    project_dir.mkdir(parents=True)
    (root / "examples").mkdir()
    (root / "AGENTS.md").write_text("instructions\n", encoding="utf-8")
    cards = [
        {
            "id": "single-card",
            "deck": "main",
            "format": "basic",
            "front": "Atomic cue?",
            "answer": "One datum",
        }
    ]
    manifest = {
        "project_id": "review-test",
        "title": "Review Test",
        "cards_file": "cards.yaml",
        "decks": [
            {
                "key": "main",
                "path": "Review::Test",
                "output": "review-test.apkg",
                "expected_count": 1,
            }
        ],
    }
    (project_dir / "cards.yaml").write_text(
        yaml.safe_dump(cards, sort_keys=False), encoding="utf-8"
    )
    (project_dir / "project.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return load_project(project_dir), project_dir


def test_review_is_complete_plain_text(tmp_path):
    project, _ = make_review_project(tmp_path)
    review = render_review(project)
    assert "Cards: 1" in review
    assert "Card 1" in review
    assert "Front: Atomic cue?" in review
    assert "Back: One datum" in review
    assert "Review hash:" in review


def test_approval_is_invalidated_by_card_change(tmp_path):
    project, project_dir = make_review_project(tmp_path)
    approval, user_example = record_approval(project, project_fingerprint(project))
    assert approval.is_file()
    assert user_example and user_example.is_file()
    require_current_approval(project)

    cards = yaml.safe_load((project_dir / "cards.yaml").read_text(encoding="utf-8"))
    cards[0]["answer"] = "Changed datum"
    (project_dir / "cards.yaml").write_text(
        yaml.safe_dump(cards, sort_keys=False), encoding="utf-8"
    )
    changed = load_project(project_dir)
    try:
        require_current_approval(changed)
    except ValueError as exc:
        assert "changed after approval" in str(exc)
    else:
        raise AssertionError("Changed cards must invalidate approval")
