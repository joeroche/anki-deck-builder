from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from .building import build_project
from .installing import DEFAULT_ANKI_PYTHON, install_project
from .models import Project, load_project
from .planning import plan_project, write_plan
from .reviewing import record_approval, require_current_approval, write_review
from .validation import validate_project


def _output_dir(project: Project, value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else project.directory / "outputs"


def _collection(project: Project, value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    if project.profile_path:
        return project.profile_path
    raise ValueError("Collection path is required via --collection or profile_path in project.yaml")


def _print_validation(report) -> None:
    print(json.dumps(report.to_dict(), indent=2))


def command_validate(args) -> int:
    project = load_project(args.project)
    report = validate_project(project)
    report.write(_output_dir(project, args.output_dir) / "validation-report.json")
    _print_validation(report)
    return 1 if report.errors else 0


def command_plan(args) -> int:
    project = load_project(args.project)
    validation = validate_project(project)
    if validation.errors:
        _print_validation(validation)
        return 1
    output = _output_dir(project, args.output_dir)
    report = plan_project(project, _collection(project, args.collection))
    write_plan(report, output / "plan-report.json")
    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


def command_build(args) -> int:
    project = load_project(args.project)
    validation = validate_project(project)
    if validation.errors:
        _print_validation(validation)
        return 1
    require_current_approval(project)
    output = _output_dir(project, args.output_dir)
    report = build_project(project, output)
    summary = {
        "project_id": report["project_id"],
        "card_count": len(report["desired_cards"]),
        "packages": [
            {"deck": package["deck_path"], "output": package["output"], "sha256": package["sha256"]}
            for package in report["packages"]
        ],
        "report": str(output / "build-report.json"),
    }
    print(json.dumps(summary, indent=2))
    return 0


def command_install(args) -> int:
    project = load_project(args.project)
    output = _output_dir(project, args.output_dir)
    validation = validate_project(project)
    validation.write(output / "validation-report.json")
    if validation.errors:
        _print_validation(validation)
        return 1
    require_current_approval(project)
    collection = _collection(project, args.collection)
    plan = plan_project(project, collection)
    write_plan(plan, output / "plan-report.json")
    if plan["errors"]:
        print(json.dumps(plan, indent=2))
        return 1
    build = build_project(project, output)
    report = install_project(
        project,
        build,
        output,
        collection,
        Path(args.anki_python).expanduser().absolute(),
    )
    summary = {
        "project_id": report["project_id"],
        "notes_added": report["notes_added"],
        "notes_updated": len(report["notes_updated"]),
        "legacy_guids_migrated": len(report["legacy_guids_migrated"]),
        "redundant_cards_removed": report["redundant_cards_removed_count"],
        "cards_moved": len(report["cards_moved"]),
        "verification": report["verification"],
        "backup": report["backup"],
        "report": str(output / "install-report.json"),
    }
    print(json.dumps(summary, indent=2))
    return 0


def command_review(args) -> int:
    project = load_project(args.project)
    validation = validate_project(project)
    if validation.errors:
        _print_validation(validation)
        return 1
    text, _ = write_review(project)
    print(text, end="")
    return 0


def command_approve(args) -> int:
    project = load_project(args.project)
    validation = validate_project(project)
    if validation.errors:
        _print_validation(validation)
        return 1
    approval, user_example = record_approval(project, args.review_hash)
    print(f"Approval recorded: {approval}")
    if user_example:
        print(f"User example saved: {user_example}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anki-builder",
        description="Validate, build, plan, and safely install manifest-backed Anki projects.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser("review")
    review.add_argument("project", help="Project directory or project.yaml")
    review.set_defaults(handler=command_review)

    approve = subparsers.add_parser("approve")
    approve.add_argument("project", help="Project directory or project.yaml")
    approve.add_argument("--review-hash", required=True)
    approve.set_defaults(handler=command_approve)

    for name, handler in (
        ("validate", command_validate),
        ("plan", command_plan),
        ("build", command_build),
        ("install", command_install),
        ("apply", command_install),
    ):
        sub = subparsers.add_parser(name)
        sub.add_argument("project", help="Project directory or project.yaml")
        sub.add_argument("--output-dir")
        if name in {"plan", "install", "apply"}:
            sub.add_argument("--collection")
        if name in {"install", "apply"}:
            sub.add_argument("--anki-python", default=str(DEFAULT_ANKI_PYTHON))
        sub.set_defaults(handler=handler)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(args.handler(args))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
