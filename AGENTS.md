# Agent Instructions

Read `README.md`, `rules/CARD_DESIGN_ADDENDUM.md`, `rules/VALIDATION.md`, and
`rules/INSTALL_SAFETY.md` before creating or installing cards.

## Non-negotiable workflow

1. Preserve the original card rules in `README.md` verbatim.
2. Put new work in a manifest-backed project under `projects/`.
3. Run `validate`, then `review`, and show the complete plain-text review to the user.
4. Never approve a deck on the user's behalf. Wait for explicit approval of the exact review hash.
5. After explicit approval, run `approve`, then `build`. Run `plan` before any requested installation.
6. Never infer a deck hierarchy from tags, filenames, or subject wording.
7. Never claim installation success from package creation or an import dialog.
8. Never write directly to Anki SQLite tables.
9. Never open a collection through Anki's API while Anki has it locked.
10. Back up and hash the collection before an installation mutates it.
11. Move existing notes by stable GUID; use the guarded legacy matcher only for
   a declared migration.
12. Remove an obsolete deck only after verifying it contains zero cards.
13. Fail closed on count, hierarchy, GUID, media, validation, or approval mismatches.
14. Verify the live collection after every install.

## Example priority

Use `examples/user/` as the active reference whenever it contains approved
user decks. Use the bundled examples only until the user has an approved deck
of their own. Never commit `examples/user/`; it may contain private material.

Card-design philosophy changes require explicit user approval. Mechanical,
validation, safety, installation, and directory improvements may proceed when
the user has authorized implementation.
