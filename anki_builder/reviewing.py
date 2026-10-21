from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from collections import Counter

from .models import CLOZE_RE, Project


APPROVAL_FILE = "review-approval.json"
REVIEW_FILE = "review.txt"


def _fingerprinted_files(project: Project) -> list[Path]:
    paths = [project.path, project.cards_file]
    paths.extend(card.media_path for card in project.cards if card.media_path)
    return sorted(set(path.resolve() for path in paths), key=str)


def project_fingerprint(project: Project) -> str:
    digest = hashlib.sha256()
    for path in _fingerprinted_files(project):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def render_review(project: Project) -> str:
    fingerprint = project_fingerprint(project)
    lines = [
        f"Deck: {project.title}",
        f"Project: {project.project_id}",
        f"Cards: {len(project.cards)}",
        f"Review hash: {fingerprint}",
    ]
    if project.study_budget_minutes:
        lines.append(f"Study budget: {project.study_budget_minutes} minutes/day")
    if project.learner_weak_topics:
        lines.append(f"Priority / Weak topics: {', '.join(project.learner_weak_topics)}")
    if project.learner_known_topics:
        lines.append(f"Mastered prerequisites (omitted): {', '.join(project.learner_known_topics)}")

    contexts = Counter(card.context for card in project.cards if card.context)
    if contexts:
        lines.append(f"Context breakdown: {dict(contexts)}")
    stages = Counter(card.stage for card in project.cards if card.stage)
    if stages:
        lines.append(f"Stage breakdown: {dict(stages)}")

    lines.append("")
    for index, card in enumerate(project.cards, start=1):
        deck_path = project.deck_map[card.deck].path
        lines.extend(
            [
                f"Card {index}",
                f"Deck: {deck_path}",
                f"Format: {card.format}",
            ]
        )
        if card.context:
            lines.append(f"Context: {card.context}")
        if card.stage:
            lines.append(f"Stage: {card.stage}")
        if card.format == "cloze":
            cue = CLOZE_RE.sub("[...]", card.prompt)
            lines.append(f"Front: {cue}")
            lines.append(f"Revealed: {card.prompt}")
            lines.append(f"Back: {card.answer}")
        else:
            lines.append(f"Front: {card.prompt}")
            lines.append(f"Back: {card.answer}")

        if card.tags:
            lines.append(f"Tags: {', '.join(card.tags)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def review_path(project: Project) -> Path:
    return project.directory / "outputs" / REVIEW_FILE


def approval_path(project: Project) -> Path:
    return project.directory / "outputs" / APPROVAL_FILE


def write_review(project: Project) -> tuple[str, Path]:
    text = render_review(project)
    path = review_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, path


def _repository_root(project: Project) -> Path | None:
    for candidate in [project.directory, *project.directory.parents]:
        if (candidate / "AGENTS.md").is_file() and (candidate / "examples").is_dir():
            return candidate
    return None


def record_approval(project: Project, supplied_hash: str) -> tuple[Path, Path | None]:
    current_hash = project_fingerprint(project)
    if supplied_hash != current_hash:
        raise ValueError(
            "Review hash does not match the current project. Run review again and obtain explicit approval."
        )
    text, _ = write_review(project)
    path = approval_path(project)
    payload = {
        "project_id": project.project_id,
        "review_hash": current_hash,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    user_example = None
    root = _repository_root(project)
    if root:
        user_example = root / "examples" / "user" / f"{project.project_id}.txt"
        user_example.parent.mkdir(parents=True, exist_ok=True)
        user_example.write_text(text, encoding="utf-8")
    return path, user_example


def require_current_approval(project: Project) -> dict:
    path = approval_path(project)
    if not path.is_file():
        raise ValueError(
            "No approval for this deck. Run review, show every card to the user, and record explicit approval."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not read approval file: {path}") from exc
    current_hash = project_fingerprint(project)
    if payload.get("review_hash") != current_hash:
        raise ValueError(
            "The deck changed after approval. Run review again and obtain explicit approval for the new hash."
        )
    return payload
