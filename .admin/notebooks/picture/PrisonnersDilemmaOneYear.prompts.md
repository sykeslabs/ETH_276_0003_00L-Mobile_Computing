# One-year mutual-silence illustration edits

Generated on 2026-10-14 with the built-in image generation tool. The notebook's model now gives mutual silence (1, 1) years, while the other endpoint outcomes remain (5, 0), (0, 5), and (4, 4). These sibling assets preserve the preceding illustrations.

## Four endpoint outcomes

Input: `PrisonnersDilemma.png`.
Saved output: `PrisonnersDilemmaOneYear.png`.

Final prompt:

> Use case: text-localization. Edit target: the attached four-panel prisoner illustration. Make only the two text corrections in the TOP LEFT mutual-silence (C, C) outcome: replace 'A: 2 years' with 'A: 1 year' and 'B: 2 years' with 'B: 1 year'. Keep A red and B blue, match font and size. Preserve every other sentence number, word, panel, character, expression, line, color, layout, tightly cropped composition, and transparent alpha background. The other outcome sentences stay A5/B0, A0/B5, A4/B4. Do not add or remove content. Output a transparent PNG matching the input composition and aspect ratio.

## Three-round example

Input: `PrisonnersDilemmaMultiStage.png`.
Saved output: `PrisonnersDilemmaMultiStageOneYear.png`.

Final prompt:

> Use case: text-localization. Edit target: the attached three-round prisoner illustration. Make only two text corrections in the LEFTMOST Round 1 mutual-silence (C, C) sentence label: replace 'A: 2 years' with 'A: 1 year' and 'B: 2 years' with 'B: 1 year'. Keep A red and B blue, match font and size. Preserve every other sentence number, word, panel, arrow, character, expression, line, color, tightly cropped composition, layout and transparent alpha background. Round 2 remains A5/B0, Round 3 remains A4/B4. Do not add or remove content. Output a transparent PNG matching the input composition and aspect ratio.
