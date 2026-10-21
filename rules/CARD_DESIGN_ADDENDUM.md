# Card-Format and Difficult-Material Addendum

This addendum does not replace, weaken, reinterpret, or delete any existing
card-format rule. All original rules in `README.md` remain in force verbatim.

## 1. Default format: Basic recall

Use Basic front/back cards for ordinary material.

- Retrieve one fact, relationship, sign, formula component, classification, or
  procedural step.
- Use direct brute-force recall.
- Keep the answer to one recalled datum.
- Do not manufacture format variety when a Basic card is already optimal.

## 2. Targeted minimal-pair sets

When two cases are commonly confused, create a balanced contrast set.

- Include at least one qualifying and one non-qualifying case.
- Change only the decisive condition.
- Use symmetrical wording, detail, and difficulty.
- Every member must remain independently answerable.
- Do not place paired cards consecutively.
- Assign every member the same `memory_target_id` and `contrast_set_id`.
- Record each member as `qualifies`, `does_not_qualify`, or another explicit
  opposing classification.

## 3. Cloze deletion

Use cloze only when surrounding context is necessary to provide a precise cue
for a difficult relationship.

- One hidden memory target per generated card.
- Hide the smallest meaningful answer.
- The remaining sentence must provide a precise but non-revealing cue.
- Grammar, word length, punctuation, and sentence shape must not reveal the
  answer.
- Do not copy long passages and blank one word.
- Do not create several independent deletions on one card.
- Do not use cloze merely because it is faster to generate.

## 4. Variable-cue reinforcement

For the hardest or repeatedly missed target, create two or at most three atomic
cards that retrieve the same datum from genuinely different cues.

- Give every variant the same `memory_target_id` and `reinforcement_set_id`.
- Vary the retrieval route, not merely the wording.
- Keep the same single recalled datum.
- Use only for documented difficult material because it increases review load.

## 5. Type-in-the-answer cards

Use typed answers only when exact short production matters: formulas, symbols,
signs, constants, or short technical names. Never require prose, derivations,
or multi-step calculations.

## 6. Image Occlusion

Use Image Occlusion only when spatial placement or visual structure is itself
part of the target. Hide one label, region, vector, or structural feature per
card and preserve enough context to identify the diagram.

## 7. Bidirectional recall

Create both directions only when each direction is independently useful. Write
and validate each direction explicitly; never automatically reverse every card.

## 8. Format-selection order

1. Basic recall for ordinary facts.
2. Minimal pairs for known confusions.
3. Cloze for difficult contextual or relational facts.
4. Variable-cue reinforcement for the hardest memory targets.
5. Type-in cards when exact production matters.
6. Image Occlusion when spatial structure matters.
7. Bidirectional cards only when both directions are useful.

## 9. Prohibited patterns

- Recognition-only multiple choice
- Long passages with an obvious missing word
- Clozes answerable through grammar alone (including revealing `a`/`an` articles)
- Multiple unrelated blanks
- Unnecessary automatic reversals
- Images with multiple targets hidden together
- Superficial paraphrase duplicates
- Multi-step calculations, novel problem solving, explanatory answers, or essays
- Format variety added only for appearance

## 10. Knowledge calibration, answer burden, and study contexts

- **Calibrate Knowledge Worth Carding:** Distinguish demonstrated weaknesses, important untested knowledge, already-mastered prerequisites, and reference material provided during tests. Prioritize useful retrieval targets. Do not fill a chapter quota with elementary facts the learner already knows. Record deliberate omissions.
- **Short Answer Burden (Soft 5-Word Threshold):** Prefer one short recalled datum (typically $\le 5$ words). When the natural answer becomes a sentence, first try moving defining conditions into the prompt cue and retrieving the term. Use cloze when context is necessary. Preserve meaning and scientific rigor without creating essay answers.
- **Declare Study Context Early:** Route cards by what answering requires: mental recall (`phone`), handwriting (`pen_and_paper`), or a full screen (`desktop`). Settle the approved hierarchy explicitly by modality so mobile sessions aren't derailed by cards needing scratch paper.

## 11. Research basis

The addendum operationalizes retrieval practice, repeated spaced retrieval,
generation, variable retrieval cues, and interleaving. Cloze and Image
Occlusion are treated as delivery formats rather than inherently superior
learning methods.

- Karpicke & Roediger (2008), DOI `10.1126/science.1152408`
- Slamecka & Graf (1978), DOI `10.1037/0278-7393.4.6.592`
- Taylor & Rohrer (2010), DOI `10.1002/acp.1598`
- Butler et al. (2017), DOI `10.1037/xap0000142`
- Butowska-Buczyńska et al. (2024), DOI `10.1073/pnas.2413511121`
- Rawson et al. (2018), PMID `29431462`
- Anki Manual: `https://docs.ankiweb.net/editing.html`
