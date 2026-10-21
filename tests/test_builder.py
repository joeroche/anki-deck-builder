from __future__ import annotations

from pathlib import Path
import base64
import json
import subprocess

import genanki
import yaml

from anki_builder.building import build_project
from anki_builder.installing import DEFAULT_ANKI_PYTHON, install_project
from anki_builder.models import load_project, stable_guid
from anki_builder.planning import plan_project
from anki_builder.validation import validate_project


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def make_project(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "diagram.png").write_bytes(PNG_1X1)
    cards = [
        {
            "id": "pair-yes",
            "deck": "main",
            "format": "basic",
            "memory_target_id": "pair-boundary",
            "contrast_set_id": "pair-boundary",
            "contrast_role": "qualifies",
            "front": "Case A contains the decisive condition. Counts?",
            "answer": "Yes",
        },
        {
            "id": "typed-symbol",
            "deck": "main",
            "format": "typed",
            "front": "Exact symbol for change in energy?",
            "answer": "ΔE",
        },
        {
            "id": "pair-no",
            "deck": "main",
            "format": "basic",
            "memory_target_id": "pair-boundary",
            "contrast_set_id": "pair-boundary",
            "contrast_role": "does-not-qualify",
            "front": "Case B lacks the decisive condition. Counts?",
            "answer": "No",
        },
        {
            "id": "reinforcement-basic",
            "deck": "main",
            "format": "basic",
            "memory_target_id": "work-sign",
            "reinforcement_set_id": "work-sign-hard",
            "front": "Chemistry convention: sign of expansion work?",
            "answer": "Negative",
        },
        {
            "id": "image-vector",
            "deck": "main",
            "format": "image_occlusion",
            "header": "Name the hidden vector.",
            "image": "diagram.png",
            "mask": {"x": 10, "y": 10, "width": 20, "height": 20},
            "answer": "Normal force",
        },
        {
            "id": "reinforcement-cloze",
            "deck": "main",
            "format": "cloze",
            "memory_target_id": "work-sign",
            "reinforcement_set_id": "work-sign-hard",
            "text": "Expansion work has a {{c1::Negative}} sign in chemistry.",
        },
        {
            "id": "direction-forward",
            "deck": "main",
            "format": "basic",
            "memory_target_id": "directional-association",
            "bidirectional_set_id": "directional-association",
            "direction": "forward",
            "front": "Forward cue?",
            "answer": "Reverse target",
        },
        {
            "id": "standalone",
            "deck": "main",
            "format": "basic",
            "front": "Standalone atomic cue?",
            "answer": "Datum",
        },
        {
            "id": "direction-reverse",
            "deck": "main",
            "format": "basic",
            "memory_target_id": "directional-association",
            "bidirectional_set_id": "directional-association",
            "direction": "reverse",
            "front": "Reverse target?",
            "answer": "Forward cue",
        },
    ]
    (tmp_path / "cards.yaml").write_text(yaml.safe_dump(cards, sort_keys=False), encoding="utf-8")
    manifest = {
        "project_id": "test-project",
        "title": "Test Project",
        "cards_file": "cards.yaml",
        "decks": [{"key": "main", "path": "Test Parent::Prestudy", "output": "test.apkg", "expected_count": 9}],
        "installation": {"backup_before_changes": True, "remove_obsolete_decks": []},
    }
    (tmp_path / "project.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return load_project(tmp_path)


def test_all_formats_validate_and_build(tmp_path):
    project = make_project(tmp_path)
    validation = validate_project(project)
    assert not validation.errors
    output_one = tmp_path / "out-one"
    output_two = tmp_path / "out-two"
    first = build_project(project, output_one)
    second = build_project(project, output_two)
    assert first["packages"][0]["notes"] == 9
    assert first["packages"][0]["guids"] == second["packages"][0]["guids"]
    assert first["packages"][0]["deck_id"] == second["packages"][0]["deck_id"]


def test_invalid_multi_cloze_is_blocked(tmp_path):
    project = make_project(tmp_path)
    project.cards[5].raw["text"] = "{{c1::One}} and {{c2::Two}}"
    report = validate_project(project)
    assert any(issue.code == "cloze_target_count" for issue in report.errors)


def test_stable_guid_is_wording_independent():
    assert stable_guid("project", "card") == stable_guid("project", "card")
    assert stable_guid("project", "card") != stable_guid("project", "other-card")


def test_project_tag_can_be_omitted(tmp_path):
    project = make_project(tmp_path)
    assert "anki_builder::test-project" in project.cards[0].tags

    manifest_path = tmp_path / "project.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["include_project_tag"] = False
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    project = load_project(tmp_path)
    assert project.cards[0].tags == []


def test_install_is_idempotent(tmp_path):
    if not DEFAULT_ANKI_PYTHON.is_file():
        return
    project = make_project(tmp_path / "project")
    collection = tmp_path / "profile" / "collection.anki2"
    collection.parent.mkdir(parents=True)
    subprocess.run(
        [str(DEFAULT_ANKI_PYTHON), "-c", "from anki.collection import Collection; c=Collection(r'''%s'''); c.close()" % collection],
        check=True,
    )
    output = tmp_path / "built"
    build = build_project(project, output)
    first_plan = plan_project(project, collection)
    assert first_plan["summary"] == {"add": 9}
    first = install_project(project, build, output, collection)
    assert first["notes_added"] == 9
    second_plan = plan_project(project, collection)
    assert second_plan["summary"] == {"unchanged": 9}
    second = install_project(project, build, output, collection)
    assert second["notes_added"] == 0
    assert second["redundant_cards_removed_count"] == 0
    assert all(item["status"] == "skipped_all_notes_already_present" for item in second["imports"])
    assert second["verification"]["deck_counts"] == {"Test Parent::Prestudy": 9}


def test_legacy_basic_note_migrates_without_duplicate_card(tmp_path):
    if not DEFAULT_ANKI_PYTHON.is_file():
        return
    root = tmp_path / "legacy-project"
    root.mkdir(parents=True)
    cards = [{
        "id": "stable-card",
        "deck": "main",
        "format": "basic",
        "front": "Legacy front",
        "answer": "Legacy answer",
    }]
    (root / "cards.yaml").write_text(yaml.safe_dump(cards, sort_keys=False), encoding="utf-8")
    manifest = {
        "project_id": "legacy-project",
        "title": "Legacy Project",
        "cards_file": "cards.yaml",
        "decks": [{"key": "main", "path": "Legacy::Prestudy", "output": "new.apkg", "expected_count": 1}],
        "installation": {"backup_before_changes": True, "match_legacy_by_front_answer": True, "remove_obsolete_decks": []},
    }
    (root / "project.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    project = load_project(root)

    legacy_model = genanki.Model(
        1876543210,
        "Legacy Basic",
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
    )
    legacy_deck = genanki.Deck(1876543210123, "Legacy::Prestudy")
    legacy_deck.add_note(genanki.Note(model=legacy_model, fields=["Legacy front", "Legacy answer"]))
    legacy_package = tmp_path / "legacy.apkg"
    genanki.Package(legacy_deck).write_to_file(str(legacy_package))

    collection = tmp_path / "profile" / "collection.anki2"
    collection.parent.mkdir(parents=True)
    import_code = (
        "from anki.collection import Collection; "
        "from anki.import_export_pb2 import ImportAnkiPackageRequest; "
        f"c=Collection(r'''{collection}'''); "
        f"r=ImportAnkiPackageRequest(package_path=r'''{legacy_package}'''); "
        "c.import_anki_package(r); c.close()"
    )
    subprocess.run([str(DEFAULT_ANKI_PYTHON), "-c", import_code], check=True)

    output = tmp_path / "built-legacy"
    build = build_project(project, output)
    installed = install_project(project, build, output, collection)
    assert installed["notes_added"] == 0
    assert len(installed["legacy_guids_migrated"]) == 1
    assert installed["verification"]["deck_counts"] == {"Legacy::Prestudy": 1}
