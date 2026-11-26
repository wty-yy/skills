# AI Writing Patterns and Inflated-Claim Guardrails

Use this reference during Step 3 (marking tells) and Step 5 (second-pass audit). Patterns 1 to 5 and 22 justify an edit on a single sighting; patterns marked *weak alone* require accompanying tells in the same passage before rewriting, because careful human researchers sometimes use them deliberately.

## Group A: Staging Instead of Stating (Act on One Sighting)

### 1. Not X, but Y contrasts

- **Watch for**: `not X, but Y`; `not just / not only / not merely X, but Y`; `it is not X, it is Y`; `X rather than Y` when X is a straw man; split-sentence contrasts (`This does not mean X. It means Y.`); clipped negative tails (`..., no guessing`). Applies across languages (`不是……而是……`, `不仅……而且……` when empty).
- **Problem**: The negative half rejects something nobody claimed just to make the positive half sound profound. Keep a contrast only when correcting a genuine misconception in prior literature or when both halves carry distinct empirical information.
- **Rewrite**: `This approach is not merely a heuristic; it is a principled framework.` -> `This framework bounds approximation error under convex losses.`

### 2. One-line closers and dramatic fragments

- **Watch for**: Standalone one-sentence paragraphs restating the point (`That distinction matters.`, `That is the real bottleneck.`); post-example moralizing (`This shows the importance of...`, `The message was clear:`); rows of verbless fragments (`No prior. No tuning.`); closing `Overall,` or `Ultimately,` sentences that repeat the paragraph's topic claim.
- **Problem**: Tells the reader to pause for applause instead of adding evidence. Cut repetitive closers and merge fragments into complete propositions.

### 3. Pseudo-profound sayings and metaphors

- **Watch for**: `the real question is`, `at its core`, `in reality`, `what really matters`, `fundamentally`, `the heart of the matter`, `X is the Y of Z`, `X becomes a trap`, `the language of`, `the currency of`, `the architecture of` (used figuratively), `at its essence`.
- **Problem**: Dresses an ordinary research observation as an aphorism without adding specificity. Replace with the concrete mechanism or variable relationship.

### 4. Staged run-ups and unnamed "parts"

- **Watch for**: `Let's dive in`, `let's explore`, `here is what you need to know`, `now let's examine`, `to put it simply`, `honestly`, `the hard part is`, `the key part is that`, `the part that matters is`.
- **Problem**: Announces a point instead of making it, or uses `the part` instead of naming the component. State the technical claim directly.

### 5. Arguing with no one

- **Watch for**: `This isn't mainly about`, `To be clear`, `This is not to say`, `One might be tempted to`, `A naive approach would be` (when no baseline or literature actually uses it).
- **Problem**: Defends against an imaginary objection left over from drafting. Keep an alternative or objection only when it corresponds to a cited baseline, reviewer concern, or genuine design trade-off analyzed in the paper.

## Group B: Rhythm by Rule

### 6. Forced triads

- **Watch for**: Three adjectives, three verbs, three parallel examples, or three short sentences followed by a moral (`fast, scalable, and interpretable` when only two were measured).
- **Problem**: Ideas arrive in threes for rhythm rather than accuracy. Keep three items when the domain genuinely has three components (for example, `train, validation, and test splits`); otherwise merge redundant items or report only what was evaluated.

### 7. Repeated sentence openings

- **Watch for**: Three or more consecutive sentences starting with the exact same subject or demonstrative (`We... We... We...` or `This suggests... This indicates...`).
- **Problem**: Creates monotonous cadence. Vary openings with definite noun phrases (`The resulting gradient...`), participial bridges (`Taken together, ...`), or merged clauses.

### 8. Rhetorical dashes as universal connectors

- **Rule**: Avoid em-dashes, en-dashes, or spaced double-hyphens (` -- `) as loose clause connectors in prose unless matching an author's sample rate. Replace them with commas, colons, parentheses, or periods.
- **Academic safeguard**: Never touch hyphens or double-hyphens inside LaTeX numeric/page ranges (`pages 12--18`, `10--20%`), math formulas, code, URLs, or compound pre-noun modifiers.

### 9. Stacked qualifiers (*weak alone*)

- **Watch for**: `could potentially`, `might arguably`, `in some cases it may possibly`, `it is worth noting that it might`.
- **Problem**: Over-layered hedges muddy the claim. Collapse stacked qualifiers into a single calibrated academic hedge (`may`, `is consistent with`) that matches the evidence level, while strictly preserving real scope bounds (`in this cohort`, `under low-SNR regimes`).

### 10. Post-noun hyphenated pairs and modifier pileups (*weak alone*)

- **Watch for**: Keeping hyphens after the noun (`the dataset is high-quality and well-documented`) or stacking decorative buzz-compounds (`end-to-end, real-time, cutting-edge, data-driven pipeline`).
- **Problem**: Violates standard English hyphenation and pads sentences. Hyphenate compound modifiers before nouns (`a well-documented protocol`), drop hyphens after nouns (`the protocol is well documented`), and cut ornamental compounds that add no technical specification.

### 11. Empty passive voice and missing subjects (*weak alone*)

- **Watch for**: `It can be seen that`, `It was found by us that`, `Improvements were achieved`.
- **Problem**: Obscures agency or wastes words. Use direct active voice (`Table 2 shows`, `We found`, `The adapter reduces latency by 14%`), while retaining natural passive voice in Methods when the sample or apparatus is the topic (`Sections were stained with H&E`).

## Group C: Inflation, Vague Glue, and Synonym Cycling

### 12. High-frequency AI vocabulary

- **Watch for**: `additionally` (at sentence start in clusters), `align with`, `bolstered`, `crucial`, `deep dive`, `delve`, `enduring`, `enhance`, `garner`, `gate/gated/gating` (figurative only; keep neural gating or CI gates), `highlight` (verb), `interplay`, `intricate`, `intricacies`, `key` (overused adjective), `landscape` (abstract noun), `leverage` (when `use` works), `meticulous`, `meticulously`, `notably` (in clusters), `pave the way for`, `pivotal`, `quietly`, `robust` (figurative only; keep robust statistics/optimization), `showcase`, `stems from`, `tapestry`, `testament`, `underscore`, `valuable`, `vibrant`, `yielding`.
- **Problem**: Models overuse these words far above human academic baselines. Replace with plain, exact verbs and nouns.

### 13. Inflated significance and unsupported superlatives

- **Watch for (framing)**: `stands as a testament`, `a pivotal moment`, `plays a key role`, `marks a paradigm shift`, `evolving landscape`, `setting the stage for`, `indelible mark`, `the future looks bright`, stock upbeat closers.
- **Watch for (English overclaim wordlist)**: `extraordinary`, `exceptional`, `remarkable`, `unprecedented`, `revolutionary`, `groundbreaking`, `new paradigm`, `best`, `superior`, `state-of-the-art` (without benchmark proof), `proves`, `conclusively`, `perfectly`, `first` (unverified), `pioneering`, `transformative`, `breakthrough`.
- **Watch for (Chinese overclaim wordlist)**: `卓越`, `首次`, `唯一`, `最高`, `完美`, `碾压`, `遥遥领先`, `颠覆性`, `最优`.
- **Problem**: Outruns the data and triggers immediate reviewer skepticism. Soften or flag for author verification (`prove` -> `show` or `suggest`; `best / superior` -> `outperforms tested baselines on X` or `performs competitively`; `first` -> `to our knowledge, the first` only when verified, or bound to the exact setting).

### 14. Vague associations

- **Watch for**: `associated with`, `linked to`, `tied to`, `in connection with` when the exact relationship is known in the source text.
- **Problem**: Hides whether X causes, correlates with, regularizes, or parameterizes Y. State the exact relation given by the author, but never upgrade a reported correlation into causation.

### 15. Shallow `-ing` participial tails

- **Watch for**: `, highlighting...`, `, underscoring...`, `, emphasizing...`, `, ensuring...`, `, reflecting...`, `, showcasing...`, `, contributing to...`, `, fostering...` tacked onto the end of a factual sentence.
- **Problem**: Fakes analytical depth at the end of an observation. Delete the tail if it repeats the point, or rewrite it as an explicit causal or empirical clause if the author's evidence supports it.

### 16. Promotional and sales language

- **Watch for**: `boasts`, `rich` (figurative), `profound`, `exemplifies`, `commitment to`, `diverse array`, `stunning`, `seamless`, `empower`.
- **Problem**: Reads like a product brochure rather than peer-reviewed scholarship. Replace with neutral, measurable descriptions.

### 17. Borrowed unnamed authority

- **Watch for**: `experts argue`, `researchers widely believe`, `industry reports suggest`, `several studies have shown` (with zero citations in a citation-backed section).
- **Problem**: Invokes phantom consensus. Cite the specific works provided by the author, or ask the author to supply citations; never fabricate references to fill the gap.

### 18. Copula avoidance and synonym cycling

- **Watch for (copula avoidance)**: `serves as`, `stands as`, `functions as`, `operates as`, `represents a`, `features`, `offers` where `is`, `are`, or `has` is clearer.
- **Watch for (synonym cycling)**: Calling the same module `the routing layer`, `the dispatch mechanism`, and `the gating orchestrator` across three consecutive sentences.
- **Problem**: Hurts precision in technical writing. Prefer `is` / `are` / `has`, and lock one canonical term per concept throughout the manuscript.

## Group D: Formatting by Rule

### 19. Decorative bolding and bold-colon lists

- **Problem**: Bolding technical terms randomly mid-paragraph or turning prose arguments into vertical bullet lists where every bullet starts with `**Bold Label:**`. In academic manuscripts, convert decorative bold-colon lists back into cohesive paragraphs with logical transitions unless the target venue or section (such as a compact contribution summary) explicitly calls for bullets.

### 20. Decorative headings, Title Case overuse, and emojis

- **Problem**: Putting emojis, arrows, horizontal rules between every subsection, or restating the paper title at the top. Match the target template's heading capitalization (sentence case by default unless IEEE/ACM/journal style specifies otherwise) and strip all emojis.

### 21. Curly quotation marks in code or LaTeX (*weak alone*)

- **Problem**: Auto-curled quotes break LaTeX (` ``...'' ` is standard in `.tex`) or plain-text conventions. Match the manuscript's markup format.

## Group E: Chat and Draft Leftovers (Remove Outright)

### 22. Chatbot pleasantries and wrappers

- **Watch for**: `Certainly!`, `Here is the polished version:`, `Great question!`, `I hope this helps`, `Let me know if you'd like me to expand`. Never allow chat wrappers inside manuscript text or in-place file edits.

### 23. Knowledge-cutoff disclaimers and speculative gap-filling

- **Watch for**: `as of my last update`, `while specific details are scarce in available sources`, `it is likely that`. Never insert model-limitation disclaimers or plausible guesses into a paper; flag missing facts for the author instead.

### 24. Heading repeated in the opening sentence

- **Watch for**: Following `### Ablation Study` immediately with `This subsection presents our ablation study.` Start directly with what the ablation tests and shows.

### 25. Meta-narration about the document

- **Watch for**: Describing draft history (`This paragraph replaces our earlier formulation`) or narrating obvious layout (`anything unconfirmed is flagged`). Keep standard scholarly figure/table pointers (`Table 1 compares...`) concise and informative.

## Group F: Reader Context Mismatch

### 26. Re-explaining known context in reviewer rebuttals and replies

- **Watch for**: Opening a reviewer response by summarizing the reviewer's own critique for a full paragraph before answering it, or burying the concession/fix in the final line.
- **Fix**: In rebuttals and revision letters, lead directly with the answer, new experiment, or manuscript change, then give the concise evidence or line reference.

## When Not to Act

- Leave quoted source material, dataset strings, proper titles, and official benchmark or method names untouched.
- Keep specific, authentic scholarly voice: exact experimental observations, candid discussion of negative results or failure modes, and deliberate rhetorical choices attested in an author's writing sample.
- Remember that stripping AI tells is half the job: avoid turning varied prose into choppy, uniform 10-word sentences. Combine crisp claims with nuanced multi-clause explanations grounded in the author's evidence.
