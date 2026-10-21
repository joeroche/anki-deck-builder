from pathlib import Path
import base64
import json
import subprocess

import pytest
import yaml

from anki_builder.building import build_project
from anki_builder.installing import DEFAULT_ANKI_PYTHON, install_project
from anki_builder.models import load_project


def test_image_media_survives_native_import_and_managed_update(tmp_path: Path):
    if not DEFAULT_ANKI_PYTHON.is_file():
        pytest.skip("Anki runtime is unavailable")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    (project_dir / "diagram.png").write_bytes(image)
    manifest = {
        "project_id": "media-import-regression",
        "title": "Media import regression",
        "cards_file": "cards.yaml",
        "decks": [{"key": "main", "path": "Media regression", "output": "media.apkg", "expected_count": 1}],
        "installation": {"backup_before_changes": True, "match_legacy_by_front_answer": False, "remove_obsolete_decks": []},
    }
    cards = [{
        "id": "diagram", "deck": "main", "format": "image_occlusion",
        "header": "Name the hidden feature.", "image": "diagram.png", "answer": "Feature",
        "mask": {"x": 10, "y": 10, "width": 20, "height": 20},
    }]
    (project_dir / "project.yaml").write_text(yaml.safe_dump(manifest))
    (project_dir / "cards.yaml").write_text(yaml.safe_dump(cards))
    project = load_project(project_dir)
    build = build_project(project, tmp_path / "packages")
    collection = tmp_path / "collection.anki2"
    script = """
from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest
from pathlib import Path
import json,sys
col=Collection(sys.argv[1])
try:
    if sys.argv[2] != '-':
        col.import_anki_package(ImportAnkiPackageRequest(package_path=sys.argv[2]))
    nid=col.find_notes('tag:anki_builder::media-import-regression')[0]
    note=col.get_note(nid)
    assert (Path(col.media.dir()) / note['Image']).read_bytes()
    check=col.media.check()
    assert not check.missing, list(check.missing)
    assert not check.unused, list(check.unused)
    card=col.get_card(col.card_ids_of_note(nid)[0])
    assert note['Image'] in card.question()
    assert note['Image'] in card.answer()
    print(json.dumps({'notes':len(col.find_notes('tag:anki_builder::media-import-regression')), 'valid':True}))
finally:
    col.close()
"""
    def check(package: str):
        result = subprocess.run(
            [str(DEFAULT_ANKI_PYTHON), "-c", script, str(collection), package],
            check=True, capture_output=True, text=True,
        )
        assert json.loads(result.stdout)["valid"]

    check(build["packages"][0]["output"])
    (tmp_path / "install").mkdir()
    report = install_project(project, build, tmp_path / "install", collection)
    assert report["notes_added"] == 0
    check("-")
