# Evaluation results: dev split
engine source `461f56ef732ab002`, data `33a6d9137f0abb04`, 2026-11-18T18:35:15+00:00, python 3.12.14, spaCy 3.8.18, phonenumbers 9.0.43, bootstrap 1000 resamples over records (95% intervals in brackets).

## WNUT-17 (real informal text; labels PERSON only, so only PERSON is scored)
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 192 | 131 | 51.9 [42.5–61.2] | 35.4 [28.0–42.8] | 42.1 [34.1–49.2] | 41.7 [34.0–48.9] | 41.7 | 65.6 | 38.5 |
| full-strict | PERSON | 192 | 131 | 51.9 [42.5–61.2] | 35.4 [28.0–42.8] | 42.1 [34.1–49.2] | 41.7 [34.0–48.9] | 41.7 | 65.6 | 38.5 |
| balanced-two-word-rule | PERSON | 192 | 36 | 38.9 [23.3–55.0] | 7.3 [3.7–11.1] | 12.3 [6.4–17.9] | 13.5 [8.3–18.7] | 13.5 | 66.7 | 40.6 |
| patterns-only | PERSON | 192 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | PERSON | 192 | 131 | 51.9 [42.5–61.2] | 35.4 [28.0–42.8] | 42.1 [34.1–49.2] | 41.7 [34.0–48.9] | 41.7 | 65.6 | 38.5 |
Findings of other types are not scored (the corpus does not label them): full-balanced: 0, full-strict: 0, balanced-two-word-rule: 0, patterns-only: 0, ner-only: 0

## Synthetic: all entity types
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 96 | 46 | 100.0 [100.0–100.0] | 47.9 [37.5–57.5] | 64.8 [54.5–73.0] | 47.9 [37.5–57.5] | 47.9 | 100.0 | 0.0 |
| full-balanced | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-balanced | PHONE | 132 | 86 | 97.7 [93.8–100.0] | 63.6 [55.0–71.9] | 77.1 [70.0–83.1] | 65.2 [56.8–72.7] | 65.2 | 100.0 | 0.5 |
| full-balanced | CREDIT_CARD | 108 | 84 | 97.6 [93.5–100.0] | 75.9 [67.7–84.1] | 85.4 [79.4–90.7] | 77.8 [69.4–85.8] | 77.8 | 100.0 | 0.5 |
| full-balanced | ALL | 420 | 300 | 98.7 [97.2–99.7] | 70.5 [66.2–74.7] | 82.2 [79.1–85.1] | 71.4 [67.3–75.6] | 71.4 | 100.0 | 0.3 |
| full-strict | PERSON | 96 | 46 | 100.0 [100.0–100.0] | 47.9 [37.5–57.5] | 64.8 [54.5–73.0] | 47.9 [37.5–57.5] | 47.9 | 100.0 | 0.0 |
| full-strict | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-strict | PHONE | 132 | 105 | 98.1 [95.0–100.0] | 78.0 [70.7–84.7] | 86.9 [82.2–91.2] | 79.5 [72.6–86.2] | 79.5 | 100.0 | 0.4 |
| full-strict | CREDIT_CARD | 108 | 141 | 75.2 [68.0–82.0] | 98.1 [95.0–100.0] | 85.1 [80.0–89.7] | 100.0 [100.0–100.0] | 100.0 | 76.6 | 23.7 |
| full-strict | ALL | 420 | 376 | 90.2 [87.0–93.1] | 80.7 [77.3–84.1] | 85.2 [82.6–87.6] | 81.7 [78.2–85.0] | 81.7 | 91.2 | 9.3 |
| balanced-two-word-rule | PERSON | 96 | 32 | 100.0 [100.0–100.0] | 33.3 [23.5–42.7] | 50.0 [38.1–59.8] | 33.3 [23.5–42.7] | 33.3 | 100.0 | 0.0 |
| balanced-two-word-rule | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| balanced-two-word-rule | PHONE | 132 | 86 | 97.7 [93.8–100.0] | 63.6 [55.0–71.9] | 77.1 [70.0–83.1] | 65.2 [56.8–72.7] | 65.2 | 100.0 | 0.5 |
| balanced-two-word-rule | CREDIT_CARD | 108 | 84 | 97.6 [93.5–100.0] | 75.9 [67.7–84.1] | 85.4 [79.4–90.7] | 77.8 [69.4–85.8] | 77.8 | 100.0 | 0.5 |
| balanced-two-word-rule | ALL | 420 | 286 | 98.6 [97.0–99.7] | 67.1 [62.7–71.3] | 79.9 [76.4–82.8] | 68.1 [63.7–72.2] | 68.1 | 100.0 | 0.3 |
| patterns-only | PERSON | 96 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| patterns-only | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| patterns-only | PHONE | 132 | 86 | 97.7 [93.8–100.0] | 63.6 [55.0–71.9] | 77.1 [70.0–83.1] | 65.2 [56.8–72.7] | 65.2 | 100.0 | 0.5 |
| patterns-only | CREDIT_CARD | 108 | 84 | 97.6 [93.5–100.0] | 75.9 [67.7–84.1] | 85.4 [79.4–90.7] | 77.8 [69.4–85.8] | 77.8 | 100.0 | 0.5 |
| patterns-only | ALL | 420 | 254 | 98.4 [96.6–99.6] | 59.5 [55.6–63.7] | 74.2 [71.0–77.4] | 60.5 [56.4–64.4] | 60.5 | 100.0 | 0.3 |
| ner-only | PERSON | 96 | 47 | 97.9 [92.9–100.0] | 47.9 [37.5–57.5] | 64.3 [54.1–72.7] | 49.0 [38.4–58.6] | 49.0 | 100.0 | 5.4 |
| ner-only | EMAIL | 84 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 1.2 | n/a | n/a |
| ner-only | PHONE | 132 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | CREDIT_CARD | 108 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | ALL | 420 | 47 | 97.9 [92.9–100.0] | 11.0 [8.1–13.7] | 19.7 [14.9–24.1] | 11.2 [8.2–14.0] | 11.4 | 100.0 | 5.4 |

## Synthetic by group: full-balanced
| group | records | gold | pred | recall % | coverage % | precision % | excess % | FP / 1k chars | status |
|---|---|---|---|---|---|---|---|---|---|
| email | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_international | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_with_region | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_no_region | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | complete 24 |
| card | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| card_digit_context | 24 | 24 | 24 | 91.7 | 100.0 | 91.7 | 1.7 | – | complete 12, partial 12 |
| card_other_brand | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | complete 24 |
| phone_digit_suffix | 24 | 24 | 2 | 0.0 | 8.3 | 0.0 | 18.8 | – | complete 24 |
| negative_luhn_ids | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| negative_plus_chains | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| person | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| mixed | 24 | 60 | 58 | 96.7 | 96.7 | 100.0 | 0.0 | – | complete 24 |
| negative_numbers | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 8, partial 16 |
| negative_capitalised | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| negative_prose | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| nonenglish_es | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_fr | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_he | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |

## Synthetic by group: full-strict
| group | records | gold | pred | recall % | coverage % | precision % | excess % | FP / 1k chars | status |
|---|---|---|---|---|---|---|---|---|---|
| email | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_international | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_with_region | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_no_region | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | complete 24 |
| card | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| card_digit_context | 24 | 24 | 24 | 91.7 | 100.0 | 91.7 | 1.7 | – | complete 12, partial 12 |
| card_other_brand | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_digit_suffix | 24 | 24 | 24 | 79.2 | 87.5 | 79.2 | 16.3 | – | complete 24 |
| negative_luhn_ids | 24 | 0 | 24 | n/a | n/a | 0.0 | 100.0 | 24.10 | complete 24 |
| negative_plus_chains | 24 | 0 | 6 | n/a | n/a | 0.0 | 100.0 | 5.75 | complete 24 |
| person | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| mixed | 24 | 60 | 58 | 96.7 | 96.7 | 100.0 | 0.0 | – | complete 24 |
| negative_numbers | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 8, partial 16 |
| negative_capitalised | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| negative_prose | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| nonenglish_es | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_fr | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_he | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
