# Evaluation results: dev split
engine source `5443e2dee47faa8d`, data `e2fc2a62ad462ce7`, 2026-11-18T18:00:14+00:00, python 3.12.14, spaCy 3.8.18, phonenumbers 9.0.43, bootstrap 300 resamples over records (95% intervals in brackets).

## WNUT-17 (real informal text, PERSON only)
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 192 | 36 | 38.9 [23.3–55.0] | 7.3 [3.8–11.1] | 12.3 [6.5–17.8] | 13.5 [8.2–18.4] | 13.5 | 66.7 | 40.6 |
| full-balanced | ALL | 192 | 36 | 38.9 | 7.3 | 12.3 | 13.5 | 13.5 | 66.7 | 40.6 |
| full-strict | PERSON | 192 | 131 | 51.9 [43.2–60.7] | 35.4 [29.1–42.5] | 42.1 [34.8–48.7] | 41.7 [34.9–48.9] | 41.7 | 65.6 | 38.5 |
| full-strict | ALL | 192 | 131 | 51.9 | 35.4 | 42.1 | 41.7 | 41.7 | 65.6 | 38.5 |
| balanced-one-word | PERSON | 192 | 131 | 51.9 [43.2–60.7] | 35.4 [29.1–42.5] | 42.1 [34.8–48.7] | 41.7 [34.9–48.9] | 41.7 | 65.6 | 38.5 |
| balanced-one-word | ALL | 192 | 131 | 51.9 | 35.4 | 42.1 | 41.7 | 41.7 | 65.6 | 38.5 |
| patterns-only | PERSON | 192 | 0 | n/a | 0.0 [0.0–0.0] | n/a | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| patterns-only | ALL | 192 | 0 | n/a | 0.0 | n/a | 0.0 | 0.0 | n/a | n/a |
| ner-only | PERSON | 192 | 36 | 38.9 [23.3–55.0] | 7.3 [3.8–11.1] | 12.3 [6.5–17.8] | 13.5 [8.2–18.4] | 13.5 | 66.7 | 40.6 |
| ner-only | ALL | 192 | 36 | 38.9 | 7.3 | 12.3 | 13.5 | 13.5 | 66.7 | 40.6 |

## Synthetic: all entity types
| variant | type | gold | pred | precision % | recall % | F1 % | coverage recall % | any-type coverage % | overlap precision % | excess chars % |
|---|---|---|---|---|---|---|---|---|---|---|
| full-balanced | PERSON | 96 | 31 | 96.8 [89.3–100.0] | 31.2 [23.9–39.6] | 47.2 [38.2–56.4] | 31.2 [23.9–39.6] | 31.2 | 96.8 | 4.4 |
| full-balanced | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-balanced | PHONE | 108 | 84 | 100.0 [100.0–100.0] | 77.8 [69.4–85.4] | 87.5 [82.0–92.1] | 77.8 [69.4–85.4] | 77.8 | 100.0 | 0.0 |
| full-balanced | CREDIT_CARD | 84 | 84 | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.5 |
| full-balanced | ALL | 372 | 283 | 98.9 | 75.3 | 85.5 | 75.8 | 75.8 | 99.6 | 0.5 |
| full-strict | PERSON | 96 | 48 | 97.9 [92.7–100.0] | 49.0 [38.7–59.6] | 65.3 [55.4–74.2] | 49.0 [38.7–59.6] | 49.0 | 97.9 | 3.6 |
| full-strict | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| full-strict | PHONE | 108 | 84 | 100.0 [100.0–100.0] | 77.8 [69.4–85.4] | 87.5 [82.0–92.1] | 77.8 [69.4–85.4] | 77.8 | 100.0 | 0.0 |
| full-strict | CREDIT_CARD | 84 | 84 | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.5 |
| full-strict | ALL | 372 | 300 | 99.0 | 79.8 | 88.4 | 80.4 | 80.4 | 99.7 | 0.5 |
| balanced-one-word | PERSON | 96 | 48 | 97.9 [92.7–100.0] | 49.0 [38.7–59.6] | 65.3 [55.4–74.2] | 49.0 [38.7–59.6] | 49.0 | 97.9 | 3.6 |
| balanced-one-word | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| balanced-one-word | PHONE | 108 | 84 | 100.0 [100.0–100.0] | 77.8 [69.4–85.4] | 87.5 [82.0–92.1] | 77.8 [69.4–85.4] | 77.8 | 100.0 | 0.0 |
| balanced-one-word | CREDIT_CARD | 84 | 84 | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.5 |
| balanced-one-word | ALL | 372 | 300 | 99.0 | 79.8 | 88.4 | 80.4 | 80.4 | 99.7 | 0.5 |
| patterns-only | PERSON | 96 | 0 | n/a | 0.0 [0.0–0.0] | n/a | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| patterns-only | EMAIL | 84 | 84 | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.0 |
| patterns-only | PHONE | 108 | 84 | 100.0 [100.0–100.0] | 77.8 [69.4–85.4] | 87.5 [82.0–92.1] | 77.8 [69.4–85.4] | 77.8 | 100.0 | 0.0 |
| patterns-only | CREDIT_CARD | 84 | 84 | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 97.6 [93.4–100.0] | 100.0 [100.0–100.0] | 100.0 | 100.0 | 0.5 |
| patterns-only | ALL | 372 | 252 | 99.2 | 67.2 | 80.1 | 67.7 | 67.7 | 100.0 | 0.2 |
| ner-only | PERSON | 96 | 31 | 96.8 [89.3–100.0] | 31.2 [23.9–39.6] | 47.2 [38.2–56.4] | 31.2 [23.9–39.6] | 31.2 | 96.8 | 4.4 |
| ner-only | EMAIL | 84 | 0 | n/a | 0.0 [0.0–0.0] | n/a | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | PHONE | 108 | 0 | n/a | 0.0 [0.0–0.0] | n/a | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | CREDIT_CARD | 84 | 0 | n/a | 0.0 [0.0–0.0] | n/a | 0.0 [0.0–0.0] | 0.0 | n/a | n/a |
| ner-only | ALL | 372 | 31 | 96.8 | 8.1 | 14.9 | 8.1 | 8.1 | 96.8 | 4.4 |

## Synthetic by group: full-balanced
| group | records | gold | pred | recall % | coverage % | precision % | excess % | FP / 1k chars | status |
|---|---|---|---|---|---|---|---|---|---|
| email | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_international | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_with_region | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| phone_national_no_region | 24 | 24 | 0 | 0.0 | 0.0 | n/a | n/a | – | complete 24 |
| card | 24 | 24 | 24 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| card_digit_context | 24 | 24 | 24 | 91.7 | 100.0 | 91.7 | 1.7 | – | complete 12, partial 12 |
| person | 24 | 24 | 13 | 54.2 | 54.2 | 100.0 | 0.0 | – | complete 24 |
| mixed | 24 | 60 | 53 | 88.3 | 88.3 | 100.0 | 0.0 | – | complete 24 |
| negative_numbers | 24 | 0 | 1 | n/a | n/a | 0.0 | 100.0 | 0.93 | complete 10, partial 14 |
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
| person | 24 | 24 | 23 | 95.8 | 95.8 | 100.0 | 0.0 | – | complete 24 |
| mixed | 24 | 60 | 60 | 100.0 | 100.0 | 100.0 | 0.0 | – | complete 24 |
| negative_numbers | 24 | 0 | 1 | n/a | n/a | 0.0 | 100.0 | 0.93 | complete 10, partial 14 |
| negative_capitalised | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| negative_prose | 24 | 0 | 0 | n/a | n/a | n/a | n/a | 0.00 | complete 24 |
| nonenglish_es | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_fr | 24 | 48 | 36 | 75.0 | 75.0 | 100.0 | 0.0 | – | partial 24 |
| nonenglish_he | 24 | 48 | 24 | 50.0 | 50.0 | 100.0 | 0.0 | – | partial 24 |
