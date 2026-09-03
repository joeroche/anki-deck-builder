# Agent Instructions

Read `README.md`, `rules/CARD_DESIGN_ADDENDUM.md`, `rules/VALIDATION.md`, and
`rules/INSTALL_SAFETY.md` before creating or installing cards.

## Non-negotiable workflow

1. Preserve the original card rules in `README.md` verbatim.
2. Confirm that the user supplied the relevant learning material, required rigor, and required depth. Ask for missing context before drafting cards.
3. Put new work in a manifest-backed project under `projects/`.
4. Run `validate`, then `review`, and show the complete plain-text review to the user.
5. Never approve a deck on the user's behalf. Wait for explicit approval of the exact review hash.
6. After explicit approval, run `approve`, then `build`. Run `plan` before any requested installation.
7. Never infer a deck hierarchy from tags, filenames, or subject wording.
8. Never claim installation success from package creation or an import dialog.
9. Never write directly to Anki SQLite tables.
10. Never open a collection through Anki's API while Anki has it locked.
11. Back up and hash the collection before an installation mutates it.
12. Move existing notes by stable GUID; use the guarded legacy matcher only for
   a declared migration.
13. Remove an obsolete deck only after verifying it contains zero cards.
14. Fail closed on count, hierarchy, GUID, media, validation, or approval mismatches.
15. Verify the live collection after every install.

## Example priority

Use `examples/user/` as the active reference whenever it contains approved
user decks. Use the bundled examples only until the user has an approved deck
of their own. Never commit `examples/user/`; it may contain private material.

Card-design philosophy changes require explicit user approval. Mechanical,
validation, safety, installation, and directory improvements may proceed when
the user has authorized implementation.
