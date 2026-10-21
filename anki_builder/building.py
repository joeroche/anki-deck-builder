from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import html
import json
import sqlite3
import tempfile
import zipfile

import genanki

from .models import Card, Project, stable_integer
from .validation import ValidationReport, validate_project


CARD_CSS = """
.card { font-family: Arial, sans-serif; font-size: 20px; text-align: center;
        color: var(--fg, #111); background: var(--canvas, #fff); padding: 30px; }
.io-canvas { position: relative; display: inline-block; max-width: 100%; }
.io-canvas img { display: block; max-width: 100%; height: auto; }
.io-mask { position: absolute; background: #111; border: 2px solid #fff; }
""".strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_id(card_format: str) -> int:
    return stable_integer("anki-builder-model-v2", card_format, bits=31)


def _model(card_format: str) -> genanki.Model:
    if card_format == "basic":
        return genanki.Model(
            _model_id(card_format),
            "Anki Builder v2 - Basic",
            fields=[{"name": name} for name in ("Front", "Answer", "CardID", "ProjectID")],
            templates=[{
                "name": "Recall",
                "qfmt": "{{Front}}",
                "afmt": "{{FrontSide}}<hr id=answer>{{Answer}}",
            }],
            css=CARD_CSS,
        )
    if card_format == "typed":
        return genanki.Model(
            _model_id(card_format),
            "Anki Builder v2 - Typed",
            fields=[{"name": name} for name in ("Front", "Answer", "CardID", "ProjectID")],
            templates=[{
                "name": "Typed recall",
                "qfmt": "{{Front}}<br><br>{{type:Answer}}",
                "afmt": "{{Front}}<hr id=answer>{{type:Answer}}",
            }],
            css=CARD_CSS,
        )
    if card_format == "cloze":
        return genanki.Model(
            _model_id(card_format),
            "Anki Builder v2 - Cloze",
            fields=[{"name": name} for name in ("Text", "CardID", "ProjectID")],
            templates=[{
                "name": "Cloze recall",
                "qfmt": "{{cloze:Text}}",
                "afmt": "{{cloze:Text}}",
            }],
            css=CARD_CSS,
            model_type=genanki.Model.CLOZE,
        )
    if card_format == "image_occlusion":
        return genanki.Model(
            _model_id(card_format),
            "Anki Builder v2 - Image Occlusion",
            fields=[{"name": name} for name in ("Header", "Image", "Mask", "Answer", "CardID", "ProjectID")],
            templates=[{
                "name": "Occlusion recall",
                "qfmt": (
                    "{{Header}}<br><div class=io-canvas><img src=\"{{Image}}\">"
                    "<span class=io-mask style=\"{{Mask}}\"></span></div>"
                ),
                "afmt": "{{Header}}<hr id=answer>{{Answer}}<br><div class=io-canvas><img src=\"{{Image}}\"></div>",
            }],
            css=CARD_CSS,
        )
    raise ValueError(f"Unsupported card format: {card_format}")


def _mask_style(card: Card) -> str:
    mask = card.raw["mask"]
    return ";".join(
        [
            f"left:{float(mask['x']):g}%",
            f"top:{float(mask['y']):g}%",
            f"width:{float(mask['width']):g}%",
            f"height:{float(mask['height']):g}%",
        ]
    )


def _note(card: Card, models: dict[str, genanki.Model]) -> genanki.Note:
    if card.format in {"basic", "typed"}:
        fields = [card.prompt, card.answer, card.id, card.project_id]
    elif card.format == "cloze":
        fields = [str(card.raw["text"]), card.id, card.project_id]
    else:
        assert card.media_path
        # Anki discovers package media from note HTML, not bare filename fields.
        media_reference = (
            '<span hidden><img src="'
            + html.escape(card.media_path.name, quote=True)
            + '"></span>'
        )
        fields = [card.prompt + media_reference, card.media_path.name, _mask_style(card), card.answer, card.id, card.project_id]
    return genanki.Note(
        model=models[card.format],
        fields=fields,
        tags=card.tags,
        guid=card.guid,
    )


def inspect_package(path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="anki-builder-package-") as temp:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temp)
        root = Path(temp)
        database = next(
            (root / name for name in ("collection.anki21b", "collection.anki21", "collection.anki2") if (root / name).exists()),
            None,
        )
        if database is None:
            raise RuntimeError(f"No Anki database inside {path}")
        connection = sqlite3.connect(database)
        try:
            notes = connection.execute("select guid, flds from notes").fetchall()
            cards = connection.execute("select count(*) from cards").fetchone()[0]
        finally:
            connection.close()
    return {
        "notes": len(notes),
        "cards": cards,
        "guids": sorted(row[0] for row in notes),
        "empty_notes": sum(any(not part.strip() for part in row[1].split("\x1f")) for row in notes),
    }


def build_project(project: Project, output_dir: Path) -> dict:
    validation = validate_project(project)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    validation.write(output_dir / "validation-report.json")
    if validation.errors:
        raise ValueError(f"Validation failed with {len(validation.errors)} error(s)")

    models = {card_format: _model(card_format) for card_format in {card.format for card in project.cards}}
    packages = []
    for spec in project.decks:
        selected = [card for card in project.cards if card.deck == spec.key]
        deck = genanki.Deck(spec.deck_id, spec.path)
        media = []
        for card in selected:
            deck.add_note(_note(card, models))
            if card.media_path:
                media.append(str(card.media_path))
        output_path = output_dir / spec.output
        genanki.Package(deck, media_files=sorted(set(media))).write_to_file(str(output_path))
        package_check = inspect_package(output_path)
        if package_check["notes"] != len(selected) or package_check["cards"] != len(selected):
            raise RuntimeError(f"Package count mismatch for {spec.path}: {package_check}")
        if package_check["empty_notes"]:
            raise RuntimeError(f"Package contains empty fields: {output_path}")
        packages.append(
            {
                "deck_key": spec.key,
                "deck_path": spec.path,
                "deck_id": spec.deck_id,
                "output": str(output_path),
                "sha256": sha256_file(output_path),
                "notes": package_check["notes"],
                "cards": package_check["cards"],
                "guids": package_check["guids"],
            }
        )

    report = {
        "project_id": project.project_id,
        "title": project.title,
        "card_count": len(project.cards),
        "format_counts": dict(sorted(Counter(card.format for card in project.cards).items())),
        "packages": packages,
        "desired_cards": [
            {
                "id": card.id,
                "guid": card.guid,
                "deck_key": card.deck,
                "deck_path": project.deck_map[card.deck].path,
                "format": card.format,
                "front": card.prompt,
                "answer": card.answer,
                "data": card.raw,
            }
            for card in project.cards
        ],
    }
    (output_dir / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
