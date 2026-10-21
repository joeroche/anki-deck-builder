from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
import json
import re
from typing import Iterable

from .models import CLOZE_RE, SUPPORTED_FORMATS, Card, Project, normalize_text


ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    card_id: str | None = None


@dataclass
class ValidationReport:
    project_id: str
    card_count: int
    format_counts: dict[str, int]
    deck_counts: dict[str, int]
    memory_targets_with_multiple_cards: dict[str, int]
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "card_count": self.card_count,
            "format_counts": self.format_counts,
            "deck_counts": self.deck_counts,
            "memory_targets_with_multiple_cards": self.memory_targets_with_multiple_cards,
            "errors": [asdict(item) for item in self.errors],
            "warnings": [asdict(item) for item in self.warnings],
            "valid": not self.errors,
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def _issue(issues: list[Issue], severity: str, code: str, message: str, card: Card | None = None) -> None:
    issues.append(Issue(severity, code, message, card.id if card else None))


def strip_markup(text: str) -> str:
    text = re.sub(r"\\\(.*?\\\)|\\\[.*?\\\]|\$.*?\$", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
    return " ".join(text.split())


def _validate_card(card: Card, issues: list[Issue]) -> None:
    if not ID_RE.fullmatch(card.id):
        _issue(issues, "error", "invalid_card_id", f"Invalid card id: {card.id!r}", card)
    if card.format not in SUPPORTED_FORMATS:
        _issue(issues, "error", "unsupported_format", f"Unsupported format: {card.format}", card)
        return
    if not card.prompt:
        _issue(issues, "error", "empty_prompt", "Card prompt is empty", card)
    if not card.answer:
        _issue(issues, "error", "empty_answer", "Card answer is empty", card)
    prompt_words = len(strip_markup(card.prompt).split())
    answer_words = len(strip_markup(card.answer).split())
    if prompt_words > 30:
        _issue(issues, "warning", "long_prompt", "Prompt exceeds 30 words", card)
    if answer_words > 5 and not card.allow_wordy_answer:
        _issue(issues, "warning", "wordy_answer", f"Answer exceeds soft threshold of 5 words ({answer_words} words)", card)
    if answer_words > 12:
        _issue(issues, "warning", "long_answer", "Answer exceeds 12 words", card)
    if re.search(r"\b(and|also)\b|;|\n", card.answer, re.I):
        _issue(issues, "warning", "possible_multi_datum", "Answer may contain multiple datums", card)

    if card.format == "cloze":
        text = str(card.raw.get("text", ""))
        matches = CLOZE_RE.findall(text)
        if len(matches) != 1:
            _issue(issues, "error", "cloze_target_count", "Cloze must contain exactly one deletion", card)
        elif matches[0][0] != "1":
            _issue(issues, "error", "cloze_number", "Single cloze deletion must use c1", card)
        if re.search(r"\{\{c\d+::.*?::.+?\}\}", text):
            _issue(issues, "error", "cloze_hint", "Cloze hints can leak the answer and are prohibited", card)
        if m := re.search(r"\b(a|an)\s+\{\{c\d+::([^:}]+)", text, re.I):
            article = m.group(1).lower()
            target_word = m.group(2).strip().split()[0] if m.group(2).strip() else ""
            starts_vowel = bool(re.match(r"^[aeiou]", target_word, re.I))
            if (article == "a" and starts_vowel) or (article == "an" and not starts_vowel):
                _issue(issues, "warning", "cloze_article_leakage", f"Indefinite article '{article}' may leak or mismatch cloze target '{target_word}'", card)

    if card.format == "typed" and len(card.answer) > 40:
        _issue(issues, "error", "typed_answer_too_long", "Typed answer exceeds 40 characters", card)

    if card.format == "image_occlusion":
        if card.media_path is None or not card.media_path.is_file():
            _issue(issues, "error", "missing_image", "Image Occlusion source image is missing", card)
        elif card.media_path.stat().st_size == 0:
            _issue(issues, "error", "empty_image", "Image Occlusion source image is empty", card)
        mask = card.raw.get("mask")
        if not isinstance(mask, dict):
            _issue(issues, "error", "missing_mask", "Image Occlusion requires one mask object", card)
        else:
            values = []
            for key in ("x", "y", "width", "height"):
                try:
                    value = float(mask[key])
                except (KeyError, TypeError, ValueError):
                    _issue(issues, "error", "invalid_mask", f"Mask {key} must be numeric", card)
                    continue
                values.append((key, value))
            if len(values) == 4:
                data = dict(values)
                if min(data.values()) < 0 or max(data.values()) > 100:
                    _issue(issues, "error", "mask_bounds", "Mask values must be percentages from 0 to 100", card)
                if data["width"] <= 0 or data["height"] <= 0:
                    _issue(issues, "error", "mask_size", "Mask width and height must be positive", card)
                if data["x"] + data["width"] > 100 or data["y"] + data["height"] > 100:
                    _issue(issues, "error", "mask_overflow", "Mask extends beyond image bounds", card)


def validate_project(project: Project) -> ValidationReport:
    issues: list[Issue] = []
    if not ID_RE.fullmatch(project.project_id):
        _issue(issues, "error", "invalid_project_id", f"Invalid project id: {project.project_id!r}")
    if not project.title:
        _issue(issues, "error", "missing_title", "Project title is required")
    if not project.cards_file.is_file():
        _issue(issues, "error", "missing_cards_file", f"Cards file missing: {project.cards_file}")

    deck_keys = [deck.key for deck in project.decks]
    deck_paths = [deck.path for deck in project.decks]
    outputs = [deck.output for deck in project.decks]
    for label, values in (("deck key", deck_keys), ("deck path", deck_paths), ("output", outputs)):
        for value, count in Counter(values).items():
            if not value:
                _issue(issues, "error", f"empty_{label.replace(' ', '_')}", f"Empty {label}")
            if count > 1:
                _issue(issues, "error", f"duplicate_{label.replace(' ', '_')}", f"Duplicate {label}: {value}")
    for deck in project.decks:
        if not ID_RE.fullmatch(deck.key):
            _issue(issues, "error", "invalid_deck_key", f"Invalid deck key: {deck.key!r}")
        if not deck.output.endswith(".apkg"):
            _issue(issues, "error", "invalid_output", f"Deck output must end in .apkg: {deck.output}")
        if deck.expected_count < 0:
            _issue(issues, "error", "invalid_expected_count", f"Negative expected count for {deck.key}")

    seen_ids: set[str] = set()
    fronts: dict[str, Card] = {}
    deck_counts = Counter()
    targets: dict[str, list[Card]] = defaultdict(list)
    contrast_sets: dict[str, list[Card]] = defaultdict(list)
    reinforcement_sets: dict[str, list[Card]] = defaultdict(list)
    bidirectional_sets: dict[str, list[Card]] = defaultdict(list)

    for card in project.cards:
        _validate_card(card, issues)
        if card.id in seen_ids:
            _issue(issues, "error", "duplicate_card_id", f"Duplicate card id: {card.id}", card)
        seen_ids.add(card.id)
        if card.deck not in deck_keys:
            _issue(issues, "error", "unknown_deck", f"Unknown deck key: {card.deck}", card)
        deck_counts[card.deck] += 1
        normalized = normalize_text(card.prompt)
        if normalized in fronts:
            _issue(issues, "error", "duplicate_prompt", f"Duplicates prompt from {fronts[normalized].id}", card)
        else:
            fronts[normalized] = card
        targets[card.memory_target_id].append(card)
        if value := str(card.raw.get("contrast_set_id", "")).strip():
            contrast_sets[value].append(card)
        if value := str(card.raw.get("reinforcement_set_id", "")).strip():
            reinforcement_sets[value].append(card)
        if value := str(card.raw.get("bidirectional_set_id", "")).strip():
            bidirectional_sets[value].append(card)

    for deck in project.decks:
        actual = deck_counts[deck.key]
        if actual != deck.expected_count:
            _issue(issues, "error", "deck_count", f"{deck.key}: expected {deck.expected_count}, found {actual}")

    for set_id, cards in contrast_sets.items():
        roles = [str(card.raw.get("contrast_role", "")).strip() for card in cards]
        if len(cards) < 2 or any(not r for r in roles) or len(set(roles)) < 2:
            _issue(issues, "error", "unbalanced_contrast", f"Contrast set {set_id} lacks unique opposing roles")
        lengths = [max(1, len(strip_markup(card.prompt).split())) for card in cards]
        if max(lengths) / min(lengths) > 1.6:
            _issue(issues, "warning", "contrast_asymmetry", f"Contrast set {set_id} has asymmetric prompt lengths")
        if len(cards) == 2:
            ratio = SequenceMatcher(None, normalize_text(cards[0].prompt), normalize_text(cards[1].prompt)).ratio()
            if ratio < 0.35:
                _issue(issues, "warning", "contrast_wording", f"Contrast set {set_id} may change more than one decisive feature")

    for set_id, cards in reinforcement_sets.items():
        answers = {normalize_text(card.answer) for card in cards}
        target_ids = {card.memory_target_id for card in cards}
        if len(target_ids) > 1:
            _issue(issues, "error", "inconsistent_reinforcement_target", f"Reinforcement set {set_id} has inconsistent memory_target_ids: {sorted(target_ids)}")
        if len(cards) not in {2, 3}:
            _issue(issues, "error", "reinforcement_size", f"Reinforcement set {set_id} must contain 2 or 3 cards")
        if len(answers) != 1:
            _issue(issues, "error", "reinforcement_answer", f"Reinforcement set {set_id} must share one answer")

    for set_id, cards in bidirectional_sets.items():
        directions = {str(card.raw.get("direction", "")).strip() for card in cards}
        if len(cards) != 2 or directions != {"forward", "reverse"}:
            _issue(issues, "error", "bidirectional_shape", f"Bidirectional set {set_id} requires explicit forward and reverse cards")

    for target, cards in targets.items():
        if len(cards) > 1:
            declared = all(
                card.raw.get("contrast_set_id")
                or card.raw.get("reinforcement_set_id")
                or card.raw.get("bidirectional_set_id")
                for card in cards
            )
            if not declared:
                _issue(issues, "warning", "undeclared_repeat", f"Memory target {target} has {len(cards)} cards without a declared set")

    for previous, current in zip(project.cards, project.cards[1:]):
        previous_set = str(previous.raw.get("contrast_set_id", "")).strip()
        current_set = str(current.raw.get("contrast_set_id", "")).strip()
        if previous.deck == current.deck and previous_set and previous_set == current_set:
            _issue(
                issues,
                "error",
                "adjacent_contrast",
                f"Contrast-set cards {previous.id} and {current.id} are consecutive",
                current,
            )

    return ValidationReport(
        project_id=project.project_id,
        card_count=len(project.cards),
        format_counts=dict(sorted(Counter(card.format for card in project.cards).items())),
        deck_counts={key: deck_counts[key] for key in deck_keys},
        memory_targets_with_multiple_cards={key: len(value) for key, value in targets.items() if len(value) > 1},
        issues=issues,
    )
