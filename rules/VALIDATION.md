# Validation Rules

Validation is blocking unless an item is explicitly reported as a warning.

The validator checks:

- Manifest and card-file structure
- Unique project, deck, and card identifiers
- Exact expected counts for every deck
- Empty fields and normalized duplicate prompts
- One recalled datum and concise-answer heuristics
- Format-specific fields and limits
- Balanced contrast-set roles and wording symmetry
- Reinforcement sets of two or three cards with one shared answer
- Explicit two-direction bidirectional sets
- One cloze target with no hint leakage
- Existing and bounded Image Occlusion media/masks
- Review burden by format, memory target, and reinforcement set

Near-duplicate, answer-length, prompt-length, and contrast-symmetry heuristics are
warnings when they cannot be established deterministically. Errors fail closed.

Every build writes `validation-report.json` and `build-report.json`.
