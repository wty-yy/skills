# Per-Section Academic Writing Conventions

Different manuscript sections perform distinct rhetorical and evidentiary jobs. Apply the matching section rules below during drafting and polishing so sections do not bleed into one another.

## 1. Title

- **Core question**: Which concise, specific words make the paper discoverable, accurate, and defensible without overclaiming?
- **Targets**: Searchable, concrete, restrained, free of unverified `First` or `Novel` labels.
- **Effective structures**:

  - `[Core object or metric] in / through / via [mechanism or setting]`
  - `[Process or factor] shapes [outcome] in [system]`
  - `[Framework or method]: [specific technical action] for [problem]`
- **Avoid**: Empty `A Study of...` or `An Investigation into...` prefixes, stacked acronyms, and promotional hooks.

## 2. Abstract

- **Core question**: What problem or gap exists, what did we do, what did we find quantitatively, and why does it matter?
- **Recommended order**: Essential context (1 sentence) -> Exact gap (1 sentence) -> Method or design (1 to 2 sentences) -> Principal quantitative findings (1 to 2 sentences) -> Bounded implication (1 sentence).
- **Guardrails**: Include only details that govern a reader's or editor's decision to read further. Avoid undefined abbreviations, citations (unless venue permits), and inflated adjectives; overclaiming in the Abstract is judged just as strictly as in the main text.

## 3. Introduction

- **Core question**: Why does this problem matter, what is already known, where and why do existing approaches fall short, and what specific contribution does this paper make?
- **Recommended order**: Concrete domain motivation -> Prior approaches and what they establish -> Specific gap, bottleneck, or hard constraint -> Core approach and why it addresses the challenges -> Explicit, verifiable contributions mapped to paper sections.
- **Common faults to fix**:

  - Opening like an undergraduate textbook chapter (`Since the dawn of computing...`) instead of positioning a research problem.
  - Leaving the gap implicit between "what exists" and "what we built".
  - Spoiling low-level hyperparameter or result minutiae that belong in Methods or Results.
  - Listing "extensive experiments" as a standalone scientific contribution rather than stating what the experiments reveal.

## 4. Related Work

- **Core question**: How does the literature organize into thematic approaches, and how does the present work differ structurally from each stream?
- **Recommended order**: Group by technical theme or paradigm (chronological within each theme), synthesize shared assumptions, and close each group with the precise boundary that motivates the present paper.
- **Avoid**: Annotated bibliography laundry lists (`Author A did X. Author B did Y. Author C did Z.`) and unfair straw-man dismissals.

## 5. Methods

- **Core question**: Could an independent researcher reproduce the study, model, or analysis from this text plus explicitly cited protocols?
- **Recommended order**: Problem formulation or study design -> Data sources, cohort, or materials -> Architecture, intervention, or experimental procedure -> Outcome metrics and statistical or ablation protocols -> Ethics/compliance details where actually provided by the author.
- **Empty phrases to flag (replace from author notes or prompt the author)**:

  - `under standard conditions`
  - `using routine methods`
  - `data were analyzed statistically` (missing test name and threshold)
  - `differences were significant` (missing effect size, test statistic, or p-value)
  - `the model was properly tuned` (missing search scope or selection criterion)

## 6. Results / Experiments

- **Core question**: What was observed, under which experimental setup, and with what quantitative evidence?
- **Recommended order**: Experimental setup pointer -> Primary observation anchored to a Figure or Table -> Exact numbers, comparisons, and variance/significance -> Ablation or subgroup patterns.
- **Tense and voice**: Past tense for completed experimental observations (`increased`, `achieved`, `was detected`), or consistent present tense when referring to visual artifacts (`Table 2 shows`) and model properties in CS venues; keep tense internally consistent.
- **Common faults to fix**:

  - Drifting into speculative Discussion inside Results (`may reflect...`, `is likely caused by...`), except for brief intentional bridges between experiments.
  - Qualitative comparatives (`much higher than baseline`, `dramatically faster`) without citing the reported numbers.

## 7. Discussion

- **Core question**: What do the findings mean, how do they relate to prior literature, what mechanisms are plausible, and what limitations bound the conclusions?
- **Recommended order**: Concise synthesis of main findings (without copy-pasting Results numbers) -> Plausible interpretations and alignment/contrast with prior work -> Explicit methodological or data limitations -> Bounded theoretical or practical implications -> Concrete future directions.
- **Guardrails**: This is where calibrated hedging belongs. Never rewrite a correlation as an established mechanism unless causal identification was demonstrated.

## 8. Conclusion

- **Core question**: How does the work answer the goal posed in the Introduction, what is the decisive takeaway, and within what scope does it hold?
- **Recommended order**: Return to the research question -> Decisive finding and contribution -> Operational boundary or concrete next step.
- **Avoid**: Introducing uncited new claims or experiments, repeating the Abstract verbatim, or ending with generic self-congratulation (`paving the way for exciting future breakthroughs`).

## 9. Reviewer Rebuttals and Revision Letters

- **Core question**: Did we directly answer the reviewer's concern and point to the exact manuscript revision or new evidence?
- **Recommended order**: Direct answer or concession in the first sentence -> Concise empirical support or reasoning -> Exact location and text of the manuscript revision.
- **Avoid**: Sycophantic praise (`Thank you for this brilliant, insightful question!`) and lengthy restatements of background the reviewer already wrote.
