# WorldConsistMem — independent human annotation comparison (2026-11-11)

Source files:
- Reviewer 1: human_evaluation/reviewer_1/WCM_COMPLETED_ANNOTATION.csv
- Reviewer 2: human_evaluation/reviewer_2/WCM_COMPLETED_ANNOTATION.json

## Protocol and scope

The 120 matched annotations comprise 30 cases × four responses. Ratings are **correct**, **incorrect**, or **ambiguous** (Reviewer 1); Reviewer 2 used only **correct** and **incorrect**. Reviewer 2's C11-R1/R2/R3/R4 ratings were transcribed from a user-supplied screenshot (incorrect, incorrect, correct, correct), not from the original progress JSON. All evidence_sufficient and notes fields in Reviewer 2 remain blank. No adjudication was performed. Independence/blinding of reviewers is not independently verifiable from these files.

## Results

- Matched ratings: 120/120
- Exact agreement: 70/120 = 58.33%
- Cohen's unweighted kappa (three-category label union, ambiguous as its own category): 0.3363; expected chance agreement 37.22%.
- Reviewer 1: {"incorrect":19,"correct":75,"ambiguous":26}
- Reviewer 2: {"incorrect":65,"correct":55}
- Cross-tabulation (R1 rows × R2 columns):

| Reviewer 1 | Reviewer 2 correct | Reviewer 2 incorrect |
|---|---:|---:|
| correct | 53 | 22 |
| incorrect | 2 | 17 |
| ambiguous | 0 | 26 |

## Interpretation

This is **not yet a validated semantic-accuracy estimate**: category usage differs sharply, the labels have not been adjudicated, and all 120 responses are clustered within 30 cases. The 26 ambiguous-vs-incorrect differences should not be silently collapsed into errors. The dataset does not, by itself, establish F0/F1/F2/F3 arm membership or a full 150-item semantic regrading. Do not claim it resolves ICLR reviewer concerns about schema confounding, evidence sufficiency, or generalization.

## Disagreements requiring adjudication

| Case | Question | Disagreements (response IDs) |
|---|---|---|
| C02 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|s\\|0\\|1\\|0\\|1\\|_\\|0\\|0\\|1\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C02-R1, C02-R4 |
| C07 | \\|W\\|h\\|e\\|n\\| \\|w\\|a\\|s\\| \\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\| \\|s\\|m\\|0\\|1\\|3\\|4\\|_\\|0\\|0\\|0\\|:\\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\|:\\|0\\| \\|r\\|e\\|s\\|o\\|l\\|v\\|e\\|d\\|?\\| | C07-R1, C07-R4 |
| C08 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|s\\|0\\|1\\|0\\|5\\|_\\|0\\|0\\|5\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C08-R1, C08-R2 |
| C10 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|s\\|s\\|0\\|1\\|0\\|1\\|_\\|0\\|0\\|1\\|:\\|p\\|e\\|r\\|s\\|o\\|n\\|:\\|0\\| \\|l\\|e\\|a\\|v\\|e\\| \\|s\\|s\\|0\\|1\\|0\\|1\\|_\\|0\\|0\\|1\\|:\\|o\\|r\\|g\\|:\\|0\\|?\\| | C10-R2, C10-R3 |
| C11 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|o\\|w\\|n\\|e\\|r\\|s\\|h\\|i\\|p\\| \\|o\\|f\\| \\|s\\|l\\|0\\|1\\|6\\|8\\|_\\|0\\|0\\|0\\|:\\|p\\|r\\|o\\|j\\|e\\|c\\|t\\|:\\|0\\| \\|t\\|r\\|a\\|n\\|s\\|f\\|e\\|r\\|?\\| | C11-R3, C11-R4 |
| C12 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|m\\|0\\|1\\|3\\|7\\|_\\|0\\|0\\|3\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C12-R2, C12-R4 |
| C14 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|m\\|0\\|1\\|3\\|9\\|_\\|0\\|0\\|5\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C14-R3, C14-R4 |
| C15 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|o\\|w\\|n\\|e\\|r\\|s\\|h\\|i\\|p\\| \\|o\\|f\\| \\|s\\|m\\|0\\|1\\|3\\|7\\|_\\|0\\|0\\|3\\|:\\|p\\|r\\|o\\|j\\|e\\|c\\|t\\|:\\|0\\| \\|t\\|r\\|a\\|n\\|s\\|f\\|e\\|r\\|?\\| | C15-R1, C15-R2, C15-R3, C15-R4 |
| C16 | \\|W\\|h\\|e\\|n\\| \\|w\\|a\\|s\\| \\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\| \\|s\\|m\\|0\\|1\\|3\\|9\\|_\\|0\\|0\\|5\\|:\\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\|:\\|0\\| \\|r\\|e\\|s\\|o\\|l\\|v\\|e\\|d\\|?\\| | C16-R2, C16-R3 |
| C17 | \\|W\\|h\\|e\\|n\\| \\|w\\|a\\|s\\| \\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\| \\|s\\|l\\|0\\|1\\|7\\|0\\|_\\|0\\|0\\|2\\|:\\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\|:\\|0\\| \\|r\\|e\\|s\\|o\\|l\\|v\\|e\\|d\\|?\\| | C17-R1, C17-R3 |
| C18 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|l\\|0\\|1\\|7\\|2\\|_\\|0\\|0\\|4\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C18-R1, C18-R2, C18-R4 |
| C19 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|s\\|l\\|0\\|1\\|7\\|0\\|_\\|0\\|0\\|2\\|:\\|p\\|e\\|r\\|s\\|o\\|n\\|:\\|0\\| \\|l\\|e\\|a\\|v\\|e\\| \\|s\\|l\\|0\\|1\\|7\\|0\\|_\\|0\\|0\\|2\\|:\\|o\\|r\\|g\\|:\\|0\\|?\\| | C19-R3, C19-R4 |
| C21 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|l\\|0\\|1\\|7\\|3\\|_\\|0\\|0\\|5\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C21-R1, C21-R3, C21-R4 |
| C22 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|m\\|0\\|1\\|3\\|8\\|_\\|0\\|0\\|4\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C22-R1, C22-R3, C22-R4 |
| C23 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|o\\|w\\|n\\|e\\|r\\|s\\|h\\|i\\|p\\| \\|o\\|f\\| \\|s\\|l\\|0\\|1\\|7\\|1\\|_\\|0\\|0\\|3\\|:\\|p\\|r\\|o\\|j\\|e\\|c\\|t\\|:\\|0\\| \\|t\\|r\\|a\\|n\\|s\\|f\\|e\\|r\\|?\\| | C23-R1, C23-R2, C23-R3, C23-R4 |
| C24 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|s\\|0\\|1\\|0\\|4\\|_\\|0\\|0\\|4\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C24-R2, C24-R4 |
| C26 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|o\\|w\\|n\\|e\\|r\\|s\\|h\\|i\\|p\\| \\|o\\|f\\| \\|s\\|l\\|0\\|1\\|7\\|3\\|_\\|0\\|0\\|5\\|:\\|p\\|r\\|o\\|j\\|e\\|c\\|t\\|:\\|0\\| \\|t\\|r\\|a\\|n\\|s\\|f\\|e\\|r\\|?\\| | C26-R1, C26-R2, C26-R4 |
| C27 | \\|W\\|h\\|e\\|n\\| \\|w\\|a\\|s\\| \\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\| \\|s\\|l\\|0\\|1\\|6\\|8\\|_\\|0\\|0\\|0\\|:\\|c\\|o\\|n\\|f\\|l\\|i\\|c\\|t\\|:\\|0\\| \\|r\\|e\\|s\\|o\\|l\\|v\\|e\\|d\\|?\\| | C27-R2, C27-R3 |
| C28 | \\|W\\|h\\|e\\|n\\| \\|a\\|n\\|d\\| \\|h\\|o\\|w\\| \\|d\\|i\\|d\\| \\|t\\|h\\|e\\| \\|C\\|E\\|O\\| \\|o\\|f\\| \\|s\\|s\\|0\\|1\\|0\\|3\\|_\\|0\\|0\\|3\\|:\\|o\\|r\\|g\\|:\\|0\\| \\|c\\|h\\|a\\|n\\|g\\|e\\|?\\| | C28-R1, C28-R2 |
| C29 | \\|W\\|h\\|e\\|n\\| \\|d\\|i\\|d\\| \\|o\\|w\\|n\\|e\\|r\\|s\\|h\\|i\\|p\\| \\|o\\|f\\| \\|s\\|m\\|0\\|1\\|3\\|4\\|_\\|0\\|0\\|0\\|:\\|p\\|r\\|o\\|j\\|e\\|c\\|t\\|:\\|0\\| \\|t\\|r\\|a\\|n\\|s\\|f\\|e\\|r\\|?\\| | C29-R1, C29-R2, C29-R3, C29-R4 |

## Next actions

1. Lock the grading rubric: specify whether a correct scalar answer to a *when* question is semantically correct without the hidden composite output schema; distinguish factual sufficiency from tuple completeness.
2. Adjudicate all 50 disagreements with a third independent expert or a predefined consensus procedure, preserving raw labels and audit notes.
3. Audit the 30 case evidence packs and gold targets, especially temporally ambiguous ownership cases and document version identifiers.
4. Map the four responses per case to F0/F1/F2/F3 only after verifying the source manifest and randomization; never infer arm from R1–R4 ordering alone.
5. Run semantic scoring on the **full 150 matched transition items in all four arms**, then report paired effect sizes and cluster/bootstrap confidence intervals; replicate across models if possible.
