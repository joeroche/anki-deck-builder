from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import html
import json
import shutil
import sys

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _note_rows(col: Collection) -> tuple[dict[str, tuple], dict[tuple[str, str], list[tuple]]]:
    by_guid = {}
    by_front_answer = defaultdict(list)
    for nid, guid, sfld, flds in col.db.all("select id,guid,sfld,flds from notes"):
        fields = flds.split("\x1f")
        row = (int(nid), guid, sfld, fields)
        by_guid[guid] = row
        answer = fields[1] if len(fields) > 1 else ""
        by_front_answer[(_normalize(sfld), _normalize(answer))].append(row)
    return by_guid, by_front_answer


def _exact_deck_count(col: Collection, deck_name: str) -> int:
    did = col.decks.id_for_name(deck_name)
    if did is None:
        return 0
    return int(col.db.scalar("select count(*) from cards where did=?", did) or 0)


def _verify(col: Collection, payload: dict) -> dict:
    desired = payload["desired_cards"]
    by_guid, _ = _note_rows(col)
    missing = [item["guid"] for item in desired if item["guid"] not in by_guid]
    duplicate_guids = [
        guid for guid, count in col.db.all("select guid,count(*) from notes group by guid having count(*) > 1")
    ]
    deck_counts = {deck["path"]: _exact_deck_count(col, deck["path"]) for deck in payload["decks"]}
    expected = {deck["path"]: deck["expected_count"] for deck in payload["decks"]}
    mismatches = {name: {"expected": expected[name], "actual": count} for name, count in deck_counts.items() if count != expected[name]}
    obsolete = {
        name: col.decks.id_for_name(name) is not None
        for name in payload["installation"].get("remove_obsolete_decks", [])
    }
    return {
        "missing_guids": missing,
        "duplicate_guids": duplicate_guids,
        "deck_counts": deck_counts,
        "count_mismatches": mismatches,
        "obsolete_decks_still_present": [name for name, exists in obsolete.items() if exists],
        "valid": not missing and not duplicate_guids and not mismatches and not any(obsolete.values()),
    }


def _import_summary(package: Path, log: object) -> dict:
    """Keep install reports useful without embedding thousands of duplicate rows."""
    rendered = str(log)
    return {
        "package": str(package),
        "found_notes": rendered.count("found_notes:") and int(rendered.rsplit("found_notes:", 1)[1].split()[0]),
        "log_excerpt": rendered[:1000],
        "log_truncated": len(rendered) > 1000,
    }


def install(payload_path: Path) -> dict:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    collection_path = Path(payload["collection_path"]).expanduser().resolve()
    output_dir = Path(payload["output_dir"]).expanduser().resolve()
    if not collection_path.is_file():
        raise FileNotFoundError(f"Collection not found: {collection_path}")
    wal_path = Path(str(collection_path) + "-wal")
    if wal_path.exists() and wal_path.stat().st_size:
        raise RuntimeError("Collection has a non-empty WAL file; close Anki cleanly before installation")

    backup_dir = output_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"{collection_path.stem}-{stamp}{collection_path.suffix}"
    original_hash = _sha256(collection_path)
    shutil.copy2(collection_path, backup_path)
    backup_hash = _sha256(backup_path)
    if backup_hash != original_hash:
        raise RuntimeError("Collection backup hash mismatch")

    col = None
    rolled_back = False
    try:
        col = Collection(str(collection_path))
        total_notes_before = int(col.db.scalar("select count(*) from notes") or 0)
        migrated = []
        by_guid, by_front_answer = _note_rows(col)
        if payload["installation"].get("match_legacy_by_front_answer", False):
            for card in payload["desired_cards"]:
                if card["guid"] in by_guid or card["format"] != "basic":
                    continue
                matches = by_front_answer.get((_normalize(card["front"]), _normalize(card["answer"])), [])
                if len(matches) > 1:
                    raise RuntimeError(f"Multiple legacy notes match {card['id']}")
                if len(matches) == 1:
                    note = col.get_note(matches[0][0])
                    previous = note.guid
                    note.guid = card["guid"]
                    col.update_note(note)
                    migrated.append({"card_id": card["id"], "from_guid": previous, "to_guid": note.guid})
            by_guid, _ = _note_rows(col)

        preexisting_card_ids = {
            guid: set(col.card_ids_of_note(row[0]))
            for guid, row in by_guid.items()
            if guid in {card["guid"] for card in payload["desired_cards"]}
        }

        import_logs = []
        for package in payload["packages"]:
            path = Path(package["output"])
            if _sha256(path) != package["sha256"]:
                raise RuntimeError(f"Package hash mismatch: {path}")
            package_cards = [
                card for card in payload["desired_cards"]
                if card["deck_path"] == package["deck_path"]
            ]
            if package_cards and all(card["guid"] in by_guid for card in package_cards):
                import_logs.append({
                    "package": str(path),
                    "status": "skipped_all_notes_already_present",
                    "found_notes": len(package_cards),
                })
                continue
            request = ImportAnkiPackageRequest(package_path=str(path))
            request.options.merge_notetypes = True
            # Existing stable notes are updated explicitly below. Asking the
            # package importer to change a legacy note type can create an extra
            # card before the old template is retired.
            request.options.update_notes = 2
            request.options.update_notetypes = 2
            request.options.with_scheduling = False
            request.options.with_deck_configs = False
            log = col.import_anki_package(request)
            summary = _import_summary(path, log)
            summary["status"] = "imported"
            import_logs.append(summary)

        by_guid, _ = _note_rows(col)
        moved = []
        updated = []
        redundant_cards_removed: set[int] = set()
        for card in payload["desired_cards"]:
            row = by_guid.get(card["guid"])
            if row is None:
                raise RuntimeError(f"Imported card missing by GUID: {card['id']}")
            note = col.get_note(row[0])
            keys = set(note.keys())
            data = card.get("data", {})
            if card["format"] in {"basic", "typed"}:
                if "Front" not in keys or not ({"Answer", "Back"} & keys):
                    raise RuntimeError(f"{card['id']} has an incompatible existing note type")
                note["Front"] = card["front"]
                note["Answer" if "Answer" in keys else "Back"] = card["answer"]
            elif card["format"] == "cloze":
                if "Text" not in keys:
                    raise RuntimeError(f"{card['id']} is missing the Text field required for cloze")
                note["Text"] = data["text"]
            elif card["format"] == "image_occlusion":
                required = {"Header", "Image", "Mask", "Answer"}
                if not required.issubset(keys):
                    raise RuntimeError(f"{card['id']} has an incompatible Image Occlusion note type")
                mask = data["mask"]
                media_name = Path(data["image"]).name
                note["Header"] = (
                    card["front"] + '<span hidden><img src="'
                    + html.escape(media_name, quote=True) + '"></span>'
                )
                note["Image"] = Path(data["image"]).name
                note["Mask"] = ";".join([
                    f"left:{float(mask['x']):g}%",
                    f"top:{float(mask['y']):g}%",
                    f"width:{float(mask['width']):g}%",
                    f"height:{float(mask['height']):g}%",
                ])
                note["Answer"] = card["answer"]
            if "CardID" in keys:
                note["CardID"] = card["id"]
            if "ProjectID" in keys:
                note["ProjectID"] = payload["project_id"]
            if payload.get("include_project_tag", True):
                project_tag = f"anki_builder::{payload['project_id']}"
                if project_tag not in note.tags:
                    note.tags.append(project_tag)
            col.update_note(note)
            updated.append(card["id"])
            deck_id = col.decks.id(card["deck_path"])
            card_ids = list(col.card_ids_of_note(row[0]))
            preserved = preexisting_card_ids.get(card["guid"], set())
            if len(card_ids) > 1 and preserved:
                extras = [cid for cid in card_ids if cid not in preserved]
                if extras:
                    col.remove_cards_and_orphaned_notes(extras)
                    redundant_cards_removed.update(int(cid) for cid in extras)
                    card_ids = list(col.card_ids_of_note(row[0]))
            if len(card_ids) != 1:
                raise RuntimeError(f"{card['id']} generated {len(card_ids)} cards; expected exactly one")
            current_dids = {int(col.get_card(cid).did) for cid in card_ids}
            if current_dids != {int(deck_id)}:
                col.set_deck(card_ids, deck_id)
                moved.append(card["id"])

        removed_decks = []
        for name in payload["installation"].get("remove_obsolete_decks", []):
            did = col.decks.id_for_name(name)
            if did is None:
                continue
            count = int(col.db.scalar("select count(*) from cards where did=?", did) or 0)
            if count:
                raise RuntimeError(f"Refusing to remove non-empty obsolete deck {name!r}: {count} cards")
            col.decks.remove([did])
            removed_decks.append(name)

        verification = _verify(col, payload)
        if not verification["valid"]:
            raise RuntimeError(f"Live verification failed: {verification}")
        total_notes_after = int(col.db.scalar("select count(*) from notes") or 0)
        col.close()
        col = None

        col = Collection(str(collection_path))
        reopened_verification = _verify(col, payload)
        if not reopened_verification["valid"]:
            raise RuntimeError(f"Reopened verification failed: {reopened_verification}")
        col.close()
        col = None

        report = {
            "project_id": payload["project_id"],
            "collection": str(collection_path),
            "backup": str(backup_path),
            "original_sha256": original_hash,
            "backup_sha256": backup_hash,
            "notes_before": total_notes_before,
            "notes_after": total_notes_after,
            "notes_added": total_notes_after - total_notes_before,
            "legacy_guids_migrated": migrated,
            "notes_updated": updated,
            "redundant_cards_removed": sorted(redundant_cards_removed),
            "redundant_cards_removed_count": len(redundant_cards_removed),
            "cards_moved": moved,
            "decks_removed": removed_decks,
            "imports": import_logs,
            "verification": reopened_verification,
            "rolled_back": False,
        }
        (output_dir / "install-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    except Exception:
        if col is not None:
            try:
                col.close()
            except Exception:
                pass
        shutil.copy2(backup_path, collection_path)
        rolled_back = _sha256(collection_path) == original_hash
        failure = {
            "project_id": payload.get("project_id"),
            "collection": str(collection_path),
            "backup": str(backup_path),
            "rolled_back": rolled_back,
            "verification": {"valid": False},
        }
        (output_dir / "install-report.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m anki_builder.install_worker PAYLOAD.json")
    report = install(Path(sys.argv[1]))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
