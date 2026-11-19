# Corrections to an FDA briefing document

A single, fully documented case: the FDA briefing document for the Oncologic Drugs Advisory Committee meeting of 15 March 2024 on cilta-cel (CARTITUDE-4, BLA 125746/S-74, https://www.fda.gov/media/176986/download) and the erratum FDA published for it (https://www.fda.gov/media/176987/download, 19 corrections).

The question: which of the corrected numbers could a check find in the original document, without data, and does numcheck find them?

| Erratum item | Original | Corrected | Detectable from the document? | numcheck 0.2.0 |
|---|---|---|---|---|
| 7 | Table 1, Total "Not reported" 80 (19) | 74 (18) | yes: the arms add up to 74 | flagged (row_total, medium) |
| 8 | Table 1, Total "Asia" 529 (12) | 52 (12) | yes: the arms add up to 52 | flagged (row_total, medium) |
| 13 | Table 11, AST increased 25 (28) | 86 (45.7) | yes: 25 of 188 is 13 % | flagged (table_cell, medium) |
| 15 | Table 13, HLH/MAS standard therapy 1 (2) | 0 (0) | yes: 1 of 208 is 0.5 % | flagged (table_cell, medium) |
| 1 | SAEs 36 % and 37 % | 37.8 % and 38.9 % | no: no counts printed | – |
| 12 | Table 10, two rows copied from the row above | other values | no: the copied values are consistent | – |
| 13 | Table 11, ALK increased 86 (45.7) | 76 (40.7) | no: consistent with N=188 | – |
| 15 | Table 13, hematologic neoplasm 1 (0.5) | 3 (1.6) | no: consistent | – |
| 16 | Table 14, lymphopenia 6 (3.2) | 55 (29.3) | no: consistent | – |
| others | dates, wording, interim analysis number, HR text | | no | – |

All four corrected numbers that can be detected from the document are flagged. Items 13 and 15 were found only after the layout "two columns per N, empty cells printed as 0" was added in version 0.2.0 (`table_cells_spanned`); version 0.1.0 flagged items 7 and 8.

Most corrections in this erratum (copied rows, wrong but consistent values, text) cannot be found by any check that has only the document. That is the limit of this approach and the reason to compare numbers with their source.

Reproduce: download both PDFs and run `numcheck --json <briefing.pdf>`.
