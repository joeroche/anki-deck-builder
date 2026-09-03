# anki-deck-builder

AI can generate a lot of flashcards quickly. It usually generates bad ones:
overloaded prompts, vague cues, recognition questions, essay-length answers,
and duplicates that quietly inflate review time.

`anki-deck-builder` gives agents strict instructions for making focused Anki
cards. The instructions are the advantage. They require one memory target per
card, precise prompts, short answers, deliberate handling of difficult
material, blocking validation, and human approval before an Anki package is
built.

## Easiest way to use it

Paste this repository link into your coding agent of choice:

```text
https://github.com/joeroche/anki-deck-builder
```

Then paste or attach all relevant course and learning material. Include the
syllabus, learning objectives, lecture notes, textbook sections, study guides,
practice questions, and instructor guidance that should shape the deck. State
the required rigor and depth, such as high school, introductory university,
upper-level university, certification exam, or professional practice.

Give the agent this prompt with your material:

```text
Use this repository to make an Anki deck from my notes. Follow every instruction
and rule in the repository. Use all relevant course and learning information I
provide. The required rigor is [LEVEL]. The required depth is [DESCRIBE WHAT I
MUST BE ABLE TO RECALL OR DO]. Ask me for missing context if the source material,
rigor, or depth is unclear. Show me the complete proposed deck as plain text
first. Do not build the Anki file until I explicitly approve it. After I approve
it, put the finished .apkg file on my Desktop.
```

The agent should clone the repository, read its instructions, create and
validate the cards, and show you every proposed front and back as plain text.
You can approve the deck or request changes. Only after explicit approval does
the agent build the `.apkg` file on your Desktop.

Rigor tells the agent how exact and advanced the cards should be. Depth tells it
which distinctions, mechanisms, formulas, procedures, or exceptions you must
retrieve. If you do not provide both, the agent should clarify them before it
drafts the deck.

## Why it works better

- `AGENTS.md` and `rules/` constrain card design before generation starts.
- The full proposed deck is reviewed as plain text before any package is built.
- Validation blocks duplicate prompts, incorrect counts, invalid clozes,
  unbalanced contrast sets, broken media, and malformed reinforcement sets.
- Stable card identities make repeated builds and updates predictable.
- Manifests declare deck hierarchy and expected counts instead of asking the
  agent to guess.
- Installation plans changes first, backs up and hashes the collection, uses
  Anki's own APIs, and verifies the live collection afterward.
- Sanitized past decks in `examples/` give agents concrete patterns to follow.

The validator cannot judge whether a fact is true. Give the agent trustworthy
source material and check the plain-text review before approving it.

## Card format rules

These rules exist so cards produce 100% test performance, not just familiarity.

| Rule | Reason |
|------|--------|
| One atomic fact per card | Prevents cue overload; isolates weak points |
| Front = single unambiguous cue | Eliminates guessing which fact is being tested |
| Back = single recalled datum only | No reasoning, no derivation; pure recall |
| Never combine two facts on one card | Hides individual gaps during review |
| Never ask for explanations on a card | Explanations belong in practice problems |

**Correct example:**
```python
("Cation charge", "+ (positive)")
("Atomic weight: O", "16 g/mol")
("Formula: molarity = ?", "moles / liters of solution")
```

**Wrong examples:**
```python
# WRONG: two facts
("Cation vs anion charges", "Cation = +, Anion = -")

# WRONG: requires reasoning
("Why are hydrogen bonds important?", "They stabilize DNA and proteins")
```

The base rules above remain intentionally short. The addendum covers when and
how an agent may use minimal pairs, cloze deletion, variable-cue reinforcement,
typed answers, image occlusion, and bidirectional recall.

## Manual setup

Requires Python 3.11 or newer.

```bash
git clone https://github.com/joeroche/anki-deck-builder.git
cd anki-deck-builder
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Before creating cards, read `AGENTS.md`, this README, and every file in
`rules/`. Put new work in a manifest-backed directory under `projects/`. Use
the buildable projects in `examples/` as references, not as templates to copy
blindly.

## Review and approval workflow

Validate the project, then generate the full plain-text review:

```bash
anki-builder validate projects/my-deck
anki-builder review projects/my-deck
```

Show the complete review to the user. If the user requests changes, edit the
cards, validate again, and generate a new review. Never approve on the user's
behalf.

After the user explicitly approves the exact review, record that approval with
the review hash printed by the `review` command:

```bash
anki-builder approve projects/my-deck --review-hash HASH_FROM_REVIEW
anki-builder build projects/my-deck --output-dir "$HOME/Desktop"
```

Any change to the project manifest, cards, or referenced media invalidates the
approval and requires another full review.

The first approved user deck is saved as plain text under `examples/user/`.
That directory is ignored by Git. Once it contains a deck, agents must use the
user's approved decks as their active examples instead of the bundled examples.

## Project format

`project.yaml` declares identity, hierarchy, output names, and exact counts:

```yaml
project_id: example
title: Example Atomic Recall Deck
cards_file: cards.yaml
decks:
  - key: main
    path: Example::Atomic Recall
    output: example-atomic-recall.apkg
    expected_count: 3
installation:
  backup_before_changes: true
  match_legacy_by_front_answer: false
  remove_obsolete_decks: []
```

`cards.yaml` contains one YAML object per card. Stable `id` values preserve
identity even if wording changes:

```yaml
- id: tcp-transport
  deck: main
  format: basic
  front: Which transport protocol provides ordered delivery?
  answer: TCP
  tags: [example, networking]
```

See `schemas/` for the complete machine-readable formats.

## Optional safe installation

Building a package does not install it. Installation needs the Anki collection
path and a Python runtime containing Anki's Python modules:

```bash
anki-builder plan projects/my-deck \
  --collection /path/to/collection.anki2

anki-builder install projects/my-deck \
  --collection /path/to/collection.anki2
```

Close Anki before planning or installing. Installation repeats validation,
approval checking, planning, and building. It creates and hash-verifies a
backup, performs declared changes through Anki's API, and reopens the
collection to verify counts, hierarchy, identities, and cleanup.

On macOS, the CLI defaults to Anki's bundled Python runtime. Override it when
needed with `--anki-python /path/to/python-with-anki`.

## Tests

```bash
python3 -m pip install pytest
pytest
```

Most tests run with ordinary Python. Installation integration tests run only
when the configured Anki runtime is available.

## Public repository scope

This repository contains the builder, strong instructions, tests, schemas, a
generic starter project, and sanitized past examples. Personal decks,
generated packages, local profile paths, collection data, and installation
reports are excluded.
