# Installation Safety

1. Validate and build before opening an Anki collection.
2. Refuse installation when Anki is running or the collection is locked.
3. Create a timestamped collection backup before mutation.
4. Hash both the original collection and backup and require equality.
5. Use Anki's own Python collection/import APIs; never write SQLite directly.
6. Reconcile declared legacy notes before importing stable-GUID packages.
7. Import with scheduling and deck presets disabled.
8. Explicitly move every desired card to its declared deck after import.
9. Remove only declared obsolete decks, and only when exactly empty.
10. Reopen the collection and verify hierarchy, GUIDs, counts, and cleanup.
11. Write an `install-report.json` containing the backup, hashes, changes, and
    final verification.
12. A second install of unchanged input must add zero notes and preserve counts.
