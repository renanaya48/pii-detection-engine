# Detection-quality evaluation (Task 3)

Run from the repo root. Install the exact environment first (`pip install -r requirements-tested.txt`, see "Build and run" in
`SUBMISSION.md`). Verified in a fresh environment: the first three commands below regenerate the four data files
**byte-identical** to the frozen ones. The freeze check and the held-out guard need `en_core_web_sm` installed (without it
they stop with an obscure spaCy error), and they report a Python patch-version difference (the freeze records 3.12.14).
`--final` will refuse to run: the held-out split was already used once.

```
python -m evaluation.wnut17 fetch                 # download the real-text corpus (checksum-verified)
python -m evaluation.wnut17 build                 # sample 400 sentences per split
python -m evaluation.synthetic build              # generate the synthetic sets
python -m evaluation --split dev                  # development run; repeat freely
python -m evaluation --split test --final         # held-out run: once per engine version, logged
```

Outputs go to `evaluation/results/` as JSON (all numbers, error samples) and generated markdown tables.

## Protocol: what counts as development data

* **Dev** is for error analysis and for changing the engine. **Anything looked at while changing the engine
  becomes dev data**, including the regression examples in `tests/` and the first dev results.
* **Test** is measured once per engine version and not tuned on. The attempt is written to
  `results/test_runs.log` *before* any test record is scored (`status=started`) and closed as `ok` or `failed`,
  with a hash of the engine source and of the data. A second attempt on the same source hash is refused unless
  `--again` is given, and that is logged too. An interrupted or failed attempt still counts as a use.
* If the engine is changed after seeing test results, test is no longer held out and must be reported as such.
* Changes already made because of dev results are documented, not hidden: the two-word-name rule was removed from
  the `balanced` profile (`results/dev_before_name_rule.*` keeps the numbers that motivated it), and four
  synthetic groups were **added after the first dev run** because the first data could not tell the profiles apart.
  The test split had not been run at that point.

## Data

### Real text: WNUT-17 (informal, user-generated)
* Source: <https://github.com/leondz/emerging_entities_17>; the README states the data is "distributed under the
  CC-BY 4.0 license". Cite: Derczynski, Nichols, van Erp, Limsopatham (2017), *Results of the WNUT2017 Shared Task on
  Novel and Emerging Entity Recognition*, Workshop on Noisy User-generated Text, EMNLP. Files are verified by SHA-256.
* Domain: Twitter, Reddit, YouTube and StackExchange text. This is a **check on one domain** (informal prompts), not
  a general estimate of PERSON quality.
* Sample: 400 sentences from the official dev file (192 `person` mentions, seed 17) and 400 from the official test
  file (157 mentions, seed 71). `python -m evaluation.wnut17 build --n 1300` uses (nearly) the whole splits.
* Only `person` is used, so **only PERSON is scored** on this data. Findings of other types (an email in a tweet) are
  not false alarms, because the corpus does not label them; they are counted separately in the report.
* **Processed version.** The corpus is one token per line. Text is rebuilt by a simple detokenizer (spaces removed
  before punctuation and clitics, split apostrophes and Reddit HTML escapes rejoined), so it is close to, not identical
  to, the original post. Gold offsets refer to the rebuilt text.
* **Sampling unit.** The files carry no post identifiers, so records are treated as independent sentences and the
  bootstrap resamples sentences. Sentences from the same thread would be correlated, which makes the intervals
  somewhat too narrow.
* **Annotation differences.** WNUT guidelines differ from those of the model's training data. This can move scores
  in either direction; it is not necessarily a deficit of the engine.
* **Possible overlap with the model's training data cannot be ruled out.** `en_core_web_sm` was trained on OntoNotes 5
  (news, broadcast, web text), a different domain, so overlap of documents is unlikely; shared famous names are not
  by themselves leakage. I could not inspect the training data, so no stronger claim is made.

### Synthetic (all four entity types, with hard negatives)
* `synthetic.py`, seeded (dev 101, test 202), 18 groups of 24 records per split (432 each).
* **Structural split.** Dev and test share no templates, name pools, email domains or styles, card layouts, negative
  kinds, phone formats, suffixes or chain styles (`tests/test_eval_synthetic.py` enforces it). Test also holds formats
  dev never contains: ALL-CAPS and lowercase names, unbroken and hyphenated card numbers, E.164 phones, IP addresses,
  hashes and tracking IDs as negatives. Scores on test can therefore be lower for reasons of format, not tuning.
* Groups include national phones with and without a region hint (the second measures the choice not to guess a
  country), non-English text (Spanish, French, Hebrew: patterns are expected to work, NER is not, status `partial`),
  and four groups that make `strict` and `balanced` differ: real cards of brands the engine does not know,
  phone numbers followed by digits, Luhn-valid 16-digit order numbers, and random `+` digit chains.
* **Limitations.** Template text is far more regular than real text, so precision near 100% on synthetic data says
  little about real prose. Treat synthetic numbers as **unit-level evidence about specific behaviours**, and the
  WNUT numbers as the only real-text signal. The 98.7% precision / 70.5% recall of `balanced` are **synthetic dev**
  results, not an overall quality claim.

## Metrics (definitions in `metrics.py`, tested)

Per entity type; a prediction matches only a gold span of the same type unless stated.

| metric | meaning |
|---|---|
| exact precision / recall / F1 | type, start and end all equal. F1 = 2·TP / (predictions + gold), so a system that finds nothing scores 0, not "n/a" |
| coverage recall | the gold span is fully covered by same-type predictions (leak-oriented) |
| any-type coverage recall | fully covered by predictions of any type (hidden even if mislabelled) |
| overlap precision | prediction paired one-to-one with a same-type gold span (exact pairs first) |
| excess chars / over-marking | predicted characters outside the gold spans; guards against rewarding "mark everything" |
| false positives per 1,000 chars | on groups that contain no PII |

Ratios with an empty denominator are `n/a`. Intervals are 95% percentile bootstrap over records (1,000 resamples,
fixed seed); `ALL` is summed over whole records before resampling.

## Variants compared

`full-balanced` and `full-strict` (the shipped profiles), `balanced-two-word-rule` (balanced plus the removed rule, to
keep its cost visible), `patterns-only` (no NER) and `ner-only`. All share one loaded model.

## Known limits of this evaluation

* Small real-text sample (about 190 and 160 mentions): wide intervals, direction rather than fine ranking.
* No formal-text real corpus (OntoNotes is licensed), so one-word-name behaviour on formal prose is unmeasured.
* Only English is scored for PERSON; non-English groups measure the documented gap, not quality.
* Latency and memory are measured separately by `bench/` and are not part of this report.
