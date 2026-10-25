# macOS computer use: Qt table-accessibility crash

## When this applies

Use this runbook only when native Anki crashes during macOS accessibility inspection, commonly when Browse contains a selected row. Preserve the collection and unfinished sessions. Keep Anki in the background unless the user requests it in front; never repeatedly relaunch it over the user's work.

The locally confirmed signature was `EXC_BAD_ACCESS / SIGSEGV`, main/CrBrowserMain thread, `libqcocoa.dylib`, then AppKit `NSAccessibilityAttributeAccessorInfo`, `accessibilityArrayAttributeCount`, and HIServices `__AXCopyAttributeValueForHierarchy`. On the pinned binary, offset `529072` resolves to `QMacAccessibilityElement::accessibilitySelectedChildren + 204`. A superficially similar crash elsewhere needs a new diagnosis.

## Cause and scope

Synthesized Cocoa table elements borrow their parent table's Qt accessibility ID. Two Qt cleanup paths incorrectly delete that shared interface. A later selected-child query can dereference the invalid interface. The local backport implements the two ownership guards from [Qt Gerrit 765434, patch set 1](https://codereview.qt-project.org/c/qt/qtbase/+/765434/1), associated with QTBUG-149612. The candidate was **NEW, not merged**, when checked on 2026-10-25. This is a local runtime backport, not an official Anki release or a general fix for every Qt crash.

The installed backport leaves accessibility enabled and selected children exposed. It does not hide selections, disable security protections, edit Qt binaries, or access Anki collection data. An Anki add-on loads a locally compiled Objective-C library before Browse opens. All callbacks stay native; none call Python from object destruction. Removal of the add-on followed by restart restores the original behavior.

The only supported pin is macOS arm64, Qt **6.9.1**, with Cocoa-plugin SHA-256:

```
e55f65197f5a3c2520a65190930f5051f5d5d7b1e861821d36c1838a556b977d
```

The observed Anki version was 25.9.4. The loader verifies both the expected plugin file and the image that actually owns the runtime accessibility class. It refuses unknown hashes, architectures, versions, class layouts, missing Qt functions, incompatible method signatures, and installation away from the GUI thread. Do not widen the pin merely because another Qt version has the same class name. The wrappers rely on Qt's GUI-thread confinement.

## Apply or inspect

Run from the repository root. Python 3 and Apple's installed command-line compiler are required. The helper locates the normal Anki Python runtime and base directory beneath the current user's Library; use `--anki-python` or `--anki-base` for a different installation.

```sh
python3 tools/macos_qt_guard/manage.py inspect
python3 tools/macos_qt_guard/test_manage.py
```

If `supported` is false, stop this installation path. Research a supported upstream runtime or prepare and validate a separate backport. Blind upgrades are not a confirmed fix: the [Anki reproduction report](https://forums.ankiweb.net/t/macos-accessibility-scan-can-crash-browse-when-a-row-is-selected/70882) also reproduced the defect on Qt 6.11.2. `QT_ACCESSIBILITY=0` did not prevent the local crash.

Quit Anki normally, then:

```sh
python3 tools/macos_qt_guard/manage.py install
open -g -a Anki
python3 tools/macos_qt_guard/manage.py status
```

Installation refuses a running Anki process, compiles from the checked-in source, stages the add-on, and moves any previous installation into `Anki2/qt_guard_backups/` before replacement. It records source and library hashes. No compiled binary is committed. The installed package is `Anki2/addons21/qt_macos_ownership_guard/`.

Require runtime status `installed`, not merely an installer exit code. The runtime receipt is `user_files/status.json` inside the add-on; it includes the loaded plugin hash and counts of guarded cleanup operations. A reporting error after installation does not mean the hooks were removed; restart is required to remove them. Do not hot-reload or unload this native library while callbacks may still refer to it.

## Verify without grading cards

Prefer background checks. Obtain approval through normal task context before bringing windows forward; respect an explicit request to keep them hidden. Do not answer or grade the user's cards to test the fix.

The included native regression test creates a synthetic table, with no Anki profile or collection access. One command validates the runtime pin, compiles both libraries from source, and runs all 15 cases in the background. Anki may remain open:

```sh
python3 tools/macos_qt_guard/manage.py regression
```

For manual investigation, build the guard (`manage.py build`) and probe first:

```sh
xcrun clang -dynamiclib -fno-objc-arc -framework Foundation \
  -o tools/macos_qt_guard/native_probe.dylib \
  tools/macos_qt_guard/native_probe.m
"$HOME/Library/Application Support/AnkiProgramFiles/.venv/bin/python" \
  tools/macos_qt_guard/native_regression.py --patched --background
```

`--background` prevents application foreground transformation, avoids activation, and positions the synthetic window outside the desktop. It still uses the real Cocoa plugin, not Qt's offscreen plugin. It verifies table-ID survival, selected-cell counts and roles across 15 row/column cases (2 → 3 → 2 → 4 → 2 columns), then explicitly flushes deferred widget deletion and requires clean process exit. The unpatched control is the same command without `--patched`; it deliberately exercises the defect and must run only against synthetic data. Locally it failed on the first query: table ID disappeared and no selected cells remained. The patched run passed all 15 cases.

Also verify actual Anki Browse when non-disruptive: one selected row, repeated accessibility scans, fullscreen/windowed transitions, selection changes, and closing/reopening Browse. Confirm selected children remain exposed, check for newly timestamped crash reports, and distinguish ScreenCaptureKit capture failures from target-process crashes. Do not claim every scenario passed if it was not exercised. The local integration evidence included ten repeated Browse hierarchy scans, selected-card content, a fullscreen screenshot, and no new Anki crash after the guard. Broader accessibility behavior, spoken VoiceOver, long-term leak freedom, and every possible teardown path remain unverified.

Local card setup also rendered all 20 selected cards and 47 formula spans in a hidden Anki webview without changing review history. That is card-render evidence, separate from the ownership regression test.

For future deck setup, prefer the ordinary Anki reviewer unless the user asks for a custom study interface. A custom dialog inside Anki is not the standard reviewer; label it clearly. Verify both the requested deck and its first question through normal Anki, without answering it. Hidden MathJax rendering can check all selected formulas without bringing Browse forward. These checks do not require accessibility inspection. A card-count or render pass does not establish completion of a study session.

## Roll back and upgrades

Quit Anki, then:

```sh
python3 tools/macos_qt_guard/manage.py rollback
open -g -a Anki
```

Rollback moves the package out of `addons21` into a dated backup; it does not delete it or touch collection data. It is idempotent. A future Anki/Qt update may make the pin fail closed. Reinspect first; remove this local backport once a supported upstream fix passes the same regression and real-UI checks. Never remove an ordinary collection backup or resolve an AnkiWeb Upload/Download conflict as part of this repair.

## Source references

- [Qt 6.9.1 Cocoa implementation](https://github.com/qt/qtbase/blob/v6.9.1/src/plugins/platforms/cocoa/qcocoaaccessibilityelement.mm)
- [Qt ownership candidate and regression test](https://codereview.qt-project.org/c/qt/qtbase/+/765434/1)
- [Anki selected-row reproduction and upstream discussion](https://forums.ankiweb.net/t/macos-accessibility-scan-can-crash-browse-when-a-row-is-selected/70882)
