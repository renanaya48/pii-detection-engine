# Evaluation results: test split
engine source `461f56ef732ab002`, data `db2eeab9060c4ebd`, 2026-11-18T18:50:01+00:00, python 3.12.14, spaCy 3.8.18, phonenumbers 9.0.43, bootstrap 1000 resamples over records (95% intervals in brackets).

## WNUT-17 (real informal text; labels PERSON only, so only PERSON is scored)
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 157 | 132 | 35.6 [27.3–44.5] | 29.9 [22.4–38.1] | 32.5 [25.4–40.6] | 36.3 [28.6–44.8] | 36.3 | 47.7 | 64.7 |
| full-strict | PERSON | 157 | 132 | 35.6 [27.3–44.5] | 29.9 [22.4–38.1] | 32.5 [25.4–40.6] | 36.3 [28.6–44.8] | 36.3 | 47.7 | 64.7 |
| balanced-two-word-rule | PERSON | 157 | 59 | 30.5 [18.5–43.8] | 11.5 [6.4–17.9] | 16.7 [9.6–25.0] | 17.8 [11.2–25.0] | 17.8 | 49.2 | 66.8 |
| patterns-only | PERSON | 157 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | PERSON | 157 | 132 | 35.6 [27.3–44.5] | 29.9 [22.4–38.1] | 32.5 [25.4–40.6] | 36.3 [28.6–44.8] | 36.3 | 47.7 | 64.7 |
Findings of other types are not scored (the corpus does not label them): full-balanced: 0, full-strict: 0, balanced-two-word-rule: 0, patterns-only: 0, ner-only: 0

## Synthetic: all entity types
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 128 | 51 | 31.4 [18.8–44.9] | 12.5 [6.8–18.2] | 17.9 [10.0–25.3] | 12.5 [6.8–18.2] | 12.5 | 62.7 | 24.3 |
| full-balanced | EMAIL | 56 | 56 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-balanced | PHONE | 172 | 138 | 96.4 [93.2–99.2] | 77.3 [71.0–83.6] | 85.8 [81.4–90.1] | 78.5 [72.5–84.8] | 78.5 | 97.8 | 3.8 |
| full-balanced | CREDIT_CARD | 104 | 80 | 100.0 [100.0–100.0] | 76.9 [68.5–85.4] | 87.0 [81.3–92.1] | 76.9 [68.5–85.4] | 76.9 | 100.0 | 0.0 |
| full-balanced | ALL | 460 | 325 | 87.7 [84.1–91.8] | 62.0 [58.6–65.4] | 72.6 [69.5–75.7] | 62.4 [59.0–65.9] | 62.4 | 93.2 | 3.4 |
| full-strict | PERSON | 128 | 51 | 31.4 [18.8–44.9] | 12.5 [6.8–18.2] | 17.9 [10.0–25.3] | 12.5 [6.8–18.2] | 12.5 | 62.7 | 24.3 |
| full-strict | EMAIL | 56 | 56 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-strict | PHONE | 172 | 149 | 96.0 [92.8–98.8] | 83.1 [77.6–88.5] | 89.1 [85.1–92.7] | 84.3 [78.8–89.6] | 84.3 | 97.3 | 4.2 |
| full-strict | CREDIT_CARD | 104 | 135 | 77.0 [69.7–83.9] | 100.0 [100.0–100.0] | 87.0 [82.1–91.3] | 100.0 [100.0–100.0] | 100.0 | 77.0 | 24.1 |
| full-strict | ALL | 460 | 391 | 81.6 [77.6–85.6] | 69.3 [66.0–73.0] | 75.0 [72.0–78.1] | 69.8 [66.5–73.3] | 69.8 | 86.2 | 11.7 |
| balanced-two-word-rule | PERSON | 128 | 22 | 72.7 [52.4–91.3] | 12.5 [6.8–18.2] | 21.3 [12.2–29.7] | 12.5 [6.8–18.2] | 12.5 | 77.3 | 27.2 |
| balanced-two-word-rule | EMAIL | 56 | 56 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| balanced-two-word-rule | PHONE | 172 | 138 | 96.4 [93.2–99.2] | 77.3 [71.0–83.6] | 85.8 [81.4–90.1] | 78.5 [72.5–84.8] | 78.5 | 97.8 | 3.8 |
| balanced-two-word-rule | CREDIT_CARD | 104 | 80 | 100.0 [100.0–100.0] | 76.9 [68.5–85.4] | 87.0 [81.3–92.1] | 76.9 [68.5–85.4] | 76.9 | 100.0 | 0.0 |
| balanced-two-word-rule | ALL | 460 | 296 | 96.3 [94.0–98.3] | 62.0 [58.6–65.4] | 75.4 [72.7–78.1] | 62.4 [59.0–65.9] | 62.4 | 97.3 | 2.9 |
| patterns-only | PERSON | 128 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| patterns-only | EMAIL | 56 | 56 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| patterns-only | PHONE | 172 | 138 | 96.4 [93.2–99.2] | 77.3 [71.0–83.6] | 85.8 [81.4–90.1] | 78.5 [72.5–84.8] | 78.5 | 97.8 | 3.8 |
| patterns-only | CREDIT_CARD | 104 | 80 | 100.0 [100.0–100.0] | 76.9 [68.5–85.4] | 87.0 [81.3–92.1] | 76.9 [68.5–85.4] | 76.9 | 100.0 | 0.0 |
| patterns-only | ALL | 460 | 274 | 98.2 [96.5–99.6] | 58.5 [55.0–62.3] | 73.3 [70.3–76.2] | 58.9 [55.5–62.7] | 58.9 | 98.9 | 1.4 |
| ner-only | PERSON | 128 | 52 | 30.8 [18.2–44.4] | 12.5 [6.8–18.2] | 17.8 [10.0–25.3] | 12.5 [6.8–18.2] | 12.5 | 61.5 | 29.1 |
| ner-only | EMAIL | 56 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 1.8 | n/a | n/a |
| ner-only | PHONE | 172 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | CREDIT_CARD | 104 | 0 | n/a | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | ALL | 460 | 52 | 30.8 [18.2–44.4] | 3.5 [1.8–5.2] | 6.2 [3.2–9.3] | 3.5 [1.8–5.2] | 3.7 | 61.5 | 29.1 |

## Synthetic by group: full-balanced
| group | records | gold | pred | recall % | coverage % | precision % | excess % | FP / 1k chars | status |
|---|---|---|---|---|---|---|---|---|---|
| email | 24 | 32 | 32 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 8, partial 16 |
| phone_international | 24 | 36 | 40 | 100.0 | 100.0 | 90.0 | 2.4 | – | partial 24 |
| phone_national_with_region | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | partial 24 |
| phone_national_no_region | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | partial 24 |
| card | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | partial 24 |
| card_digit_context | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 12, partial 12 |
| card_other_brand | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | complete 12, partial 12 |
| phone_digit_suffix | 24 | 24 | 11 | 37.5 | 45.8 | 81.8 | 8.0 | – | partial 24 |
| negative_luhn_ids | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 12, partial 12 |
| negative_plus_chains | 24 | 0 | 5 | n/a | n/a | 0.0 | 100.0 | 5.76 | partial 24 |
| person | 24 | 32 | 26 | 37.5 | 37.5 | 46.2 | 0.0 | – | complete 8, partial 16 |
| mixed | 24 | 72 | 60 | 72.2 | 72.2 | 86.7 | 0.2 | – | complete 8, partial 16 |
| negative_numbers | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 10, partial 14 |
| negative_capitalised | 24 | 0 | 7 | n/a | n/a | 0.0 | 100.0 | 6.67 | complete 24 |
| negative_prose | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| nonenglish_es | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_fr | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_he | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |

## Synthetic by group: full-strict
| group | records | gold | pred | recall % | coverage % | precision % | excess % | FP / 1k chars | status |
|---|---|---|---|---|---|---|---|---|---|
| email | 24 | 32 | 32 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 8, partial 16 |
| phone_international | 24 | 36 | 40 | 100.0 | 100.0 | 90.0 | 2.4 | – | partial 24 |
| phone_national_with_region | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | partial 24 |
| phone_national_no_region | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | partial 24 |
| card | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | partial 24 |
| card_digit_context | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 12, partial 12 |
| card_other_brand | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 12, partial 12 |
| phone_digit_suffix | 24 | 24 | 24 | 79.2 | 87.5 | 79.2 | 19.5 | – | partial 24 |
| negative_luhn_ids | 24 | 0 | 24 | n/a | n/a | 0.0 | 100.0 | 28.78 | complete 12, partial 12 |
| negative_plus_chains | 24 | 0 | 10 | n/a | n/a | 0.0 | 100.0 | 11.52 | partial 24 |
| person | 24 | 32 | 26 | 37.5 | 37.5 | 46.2 | 0.0 | – | complete 8, partial 16 |
| mixed | 24 | 72 | 60 | 72.2 | 72.2 | 86.7 | 0.2 | – | complete 8, partial 16 |
| negative_numbers | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 10, partial 14 |
| negative_capitalised | 24 | 0 | 7 | n/a | n/a | 0.0 | 100.0 | 6.67 | complete 24 |
| negative_prose | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| nonenglish_es | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_fr | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_he | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
