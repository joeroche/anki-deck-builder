from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import re
from typing import Any

import genanki
import yaml


SUPPORTED_FORMATS = {"basic", "cloze", "typed", "image_occlusion"}
CLOZE_RE = re.compile(r"\{\{c(\d+)::(.*?)(?:::[^{}]*?)?\}\}")


def stable_integer(namespace: str, value: str, bits: int = 63) -> int:
    digest = hashlib.blake2b(f"{namespace}\0{value}".encode(), digest_size=8).digest()
    number = int.from_bytes(digest, "big") & ((1 << bits) - 1)
    return number or 1


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def stable_guid(project_id: str, card_id: str) -> str:
    return genanki.guid_for("anki-builder-v2", project_id, card_id)


@dataclass(frozen=True)
class DeckSpec:
    key: str
    path: str
    output: str
    expected_count: int

    @property
    def deck_id(self) -> int:
        return stable_integer("anki-builder-deck-v2", self.path)


@dataclass(frozen=True)
class Card:
    id: str
    deck: str
    format: str
    raw: dict[str, Any]
    project_id: str
    project_dir: Path
    include_project_tag: bool = True

    @property
    def guid(self) -> str:
        return stable_guid(self.project_id, self.id)

    @property
    def prompt(self) -> str:
        if self.format in {"basic", "typed"}:
            return str(self.raw.get("front", "")).strip()
        if self.format == "cloze":
            return str(self.raw.get("text", "")).strip()
        return str(self.raw.get("header", "")).strip()

    @property
    def answer(self) -> str:
        if self.format in {"basic", "typed", "image_occlusion"}:
            return str(self.raw.get("answer", "")).strip()
        matches = CLOZE_RE.findall(str(self.raw.get("text", "")))
        return matches[0][1].strip() if len(matches) == 1 else ""

    @property
    def tags(self) -> list[str]:
        tags = [str(tag).strip() for tag in self.raw.get("tags", []) if str(tag).strip()]
        if self.include_project_tag:
            tags.append(f"anki_builder::{self.project_id}")
        return sorted(set(tags))

    @property
    def memory_target_id(self) -> str:
        return str(self.raw.get("memory_target_id", self.id))

    @property
    def media_path(self) -> Path | None:
        if self.format != "image_occlusion":
            return None
        value = str(self.raw.get("image", "")).strip()
        return (self.project_dir / value).resolve() if value else None

    @property
    def context(self) -> str | None:
        val = str(self.raw.get("context", "")).strip()
        return val if val else None

    @property
    def stage(self) -> str | None:
        val = str(self.raw.get("stage", "")).strip()
        return val if val else None

    @property
    def allow_wordy_answer(self) -> bool:
        return bool(self.raw.get("allow_wordy_answer", False))


@dataclass
class Project:
    project_id: str
    title: str
    path: Path
    cards_file: Path
    decks: list[DeckSpec]
    cards: list[Card]
    profile_path: Path | None = None
    installation: dict[str, Any] = field(default_factory=dict)
    include_project_tag: bool = True
    learner_known_topics: list[str] = field(default_factory=list)
    learner_weak_topics: list[str] = field(default_factory=list)
    supplied_reference_material: list[str] = field(default_factory=list)
    study_budget_minutes: int | None = None

    @property
    def directory(self) -> Path:
        return self.path.parent

    @property
    def deck_map(self) -> dict[str, DeckSpec]:
        return {deck.key: deck for deck in self.decks}


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_project(path: str | Path) -> Project:
    manifest_path = Path(path).expanduser().resolve()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "project.yaml"
    data = _read_yaml(manifest_path)
    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path} must contain a YAML object")

    project_id = str(data.get("project_id", "")).strip()
    title = str(data.get("title", "")).strip()
    include_project_tag = bool(data.get("include_project_tag", True))
    cards_value = str(data.get("cards_file", "")).strip()
    cards_file = (manifest_path.parent / cards_value).resolve()

    decks = [
        DeckSpec(
            key=str(item.get("key", "")).strip(),
            path=str(item.get("path", "")).strip(),
            output=str(item.get("output", "")).strip(),
            expected_count=int(item.get("expected_count", -1)),
        )
        for item in (data.get("decks") or [])
        if isinstance(item, dict)
    ]

    cards_data = _read_yaml(cards_file) if cards_file.exists() else []
    if not isinstance(cards_data, list):
        raise ValueError(f"{cards_file} must contain a YAML list")
    cards = []
    for item in cards_data:
        if not isinstance(item, dict):
            raise ValueError("Every card entry must be a YAML object")
        card_format = str(item.get("format", "basic")).strip()
        cards.append(
            Card(
                id=str(item.get("id", "")).strip(),
                deck=str(item.get("deck", "")).strip(),
                format=card_format,
                raw=item,
                project_id=project_id,
                project_dir=manifest_path.parent,
                include_project_tag=include_project_tag,
            )
        )

    learner_known_topics = [str(x).strip() for x in data.get("learner_known_topics") or [] if str(x).strip()]
    learner_weak_topics = [str(x).strip() for x in data.get("learner_weak_topics") or [] if str(x).strip()]
    supplied_reference_material = [str(x).strip() for x in data.get("supplied_reference_material") or [] if str(x).strip()]
    budget_raw = data.get("study_budget_minutes")
    study_budget_minutes = int(budget_raw) if budget_raw is not None else None

    profile_value = str(data.get("profile_path", "")).strip()
    profile_path = Path(profile_value).expanduser().resolve() if profile_value else None
    return Project(
        project_id=project_id,
        title=title,
        path=manifest_path,
        cards_file=cards_file,
        decks=decks,
        cards=cards,
        profile_path=profile_path,
        installation=dict(data.get("installation") or {}),
        include_project_tag=include_project_tag,
        learner_known_topics=learner_known_topics,
        learner_weak_topics=learner_weak_topics,
        supplied_reference_material=supplied_reference_material,
        study_budget_minutes=study_budget_minutes,
    )
