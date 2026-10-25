# Agent Instructions

Read `README.md`, `rules/CARD_DESIGN_ADDENDUM.md`, `rules/VALIDATION.md`, and
`rules/INSTALL_SAFETY.md` before creating or installing cards.

## Non-negotiable workflow

1. Preserve the original card rules in `README.md` verbatim.
2. Confirm that the user supplied the relevant learning material, required rigor, and required depth. Ask for missing context before drafting cards.
3. Calibrate knowledge: distinguish demonstrated weaknesses from mastered prerequisites, record deliberate omissions, and honor study time budgets.
4. Put new work in a manifest-backed project under `projects/`. Route cards by required study context (e.g. `phone` vs `pen_and_paper`).
5. Run `validate`, then `review`, and show the complete plain-text review to the user.
6. Never approve a deck on the user's behalf. Wait for explicit approval of the exact review hash.
7. After explicit approval, run `approve`, then `build`. Run `plan` before any requested installation.
8. Never infer a deck hierarchy from tags, filenames, or subject wording.
9. Never claim installation success from package creation or an import dialog.
10. Never write directly to Anki SQLite tables.
11. Never open a collection through Anki's API while Anki has it locked.
12. Back up and hash the collection before an installation mutates it.
13. Move existing notes by stable GUID; use the guarded legacy matcher only for
   a declared migration.
14. Remove an obsolete deck only after verifying it contains zero cards.
15. Fail closed on count, hierarchy, GUID, media, validation, or approval mismatches.
16. Verify the live collection after every install.

## Example priority

Use `examples/user/` as the active reference whenever it contains approved
user decks. Use the bundled examples only until the user has an approved deck
of their own. Never commit `examples/user/`; it may contain private material.

Card-design philosophy changes require explicit user approval. Mechanical,
validation, safety, installation, and directory improvements may proceed when
the user has authorized implementation.

## macOS computer use and native Anki crashes

If inspecting Anki crashes its native process, read `rules/MACOS_COMPUTER_USE.md`
before another launch. Match the actual crash log and runtime; do not blame card
content without evidence or repeat foreground relaunches. Keep native apps hidden
when the user asks to work in the background.

For the documented Qt Cocoa selected-child ownership defect, the source-built,
version-and-hash-pinned helper is `tools/macos_qt_guard/manage.py`. Follow its
inspect/install/status/regression/rollback sequence. Unknown runtimes fail closed;
do not loosen the pin, disable accessibility globally, or call a restart a root
fix. Preserve collections, review history, and active sessions. Verify real selected
children and table-ID survival without grading cards; record tested limits honestly.
