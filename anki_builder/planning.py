from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import sqlite3

from .models import Project, normalize_text


def _deck_name(value: str) -> str:
    return value.replace("\x1f", "::")


def collection_snapshot(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Anki collection not found: {path}")
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.25)
        connection.create_collation(
            "unicase",
            lambda left, right: (left.casefold() > right.casefold()) - (left.casefold() < right.casefold()),
        )
        decks = {int(row[0]): _deck_name(row[1]) for row in connection.execute("select id,name from decks")}
        notes = {}
        by_front_answer = defaultdict(list)
        for nid, guid, sfld, flds in connection.execute("select id,guid,sfld,flds from notes"):
            fields = flds.split("\x1f")
            item = {"id": int(nid), "guid": guid, "front": sfld, "fields": fields}
            notes[guid] = item
            answer = fields[1] if len(fields) > 1 else ""
            by_front_answer[(normalize_text(sfld), normalize_text(answer))].append(item)
        deck_cards = Counter()
        note_decks = defaultdict(set)
        for nid, did in connection.execute("select nid,did from cards"):
            deck_cards[int(did)] += 1
            note_decks[int(nid)].add(int(did))
        connection.close()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"Could not read collection; close Anki and retry: {exc}") from exc
    return {
        "decks": decks,
        "notes": notes,
        "by_front_answer": by_front_answer,
        "deck_cards": dict(deck_cards),
        "note_decks": {key: value for key, value in note_decks.items()},
    }


def plan_project(project: Project, collection_path: Path) -> dict:
    snapshot = collection_snapshot(collection_path)
    desired_paths = {deck.key: deck.path for deck in project.decks}
    deck_ids_by_name = {name: did for did, name in snapshot["decks"].items()}
    legacy_match = bool(project.installation.get("match_legacy_by_front_answer", False))
    actions = []
    errors = []

    for card in project.cards:
        target_path = desired_paths[card.deck]
        existing = snapshot["notes"].get(card.guid)
        if existing:
            current = sorted(snapshot["decks"].get(did, f"<unknown:{did}>") for did in snapshot["note_decks"].get(existing["id"], set()))
            action = "unchanged" if current == [target_path] else "move_or_update"
            actions.append({"card_id": card.id, "guid": card.guid, "action": action, "from": current, "to": target_path})
            continue

        candidates = []
        if legacy_match and card.format == "basic":
            candidates = snapshot["by_front_answer"].get(
                (normalize_text(card.prompt), normalize_text(card.answer)), []
            )
        if len(candidates) == 1:
            current = sorted(snapshot["decks"].get(did, f"<unknown:{did}>") for did in snapshot["note_decks"].get(candidates[0]["id"], set()))
            actions.append({
                "card_id": card.id,
                "guid": card.guid,
                "action": "migrate_legacy_guid_and_move",
                "legacy_guid": candidates[0]["guid"],
                "from": current,
                "to": target_path,
            })
        elif len(candidates) > 1:
            errors.append(f"{card.id}: multiple legacy notes match its front and answer")
        else:
            actions.append({"card_id": card.id, "guid": card.guid, "action": "add", "from": [], "to": target_path})

    obsolete = []
    for name in project.installation.get("remove_obsolete_decks", []):
        did = deck_ids_by_name.get(name)
        obsolete.append({
            "deck": name,
            "exists": did is not None,
            "current_cards": snapshot["deck_cards"].get(did, 0) if did is not None else 0,
            "action": "remove_after_moves_if_empty" if did is not None else "none",
        })

    summary = Counter(item["action"] for item in actions)
    return {
        "project_id": project.project_id,
        "collection": str(collection_path),
        "summary": dict(sorted(summary.items())),
        "actions": actions,
        "obsolete_decks": obsolete,
        "errors": errors,
        "safe_to_install": not errors,
    }


def write_plan(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
