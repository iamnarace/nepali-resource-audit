# Findings from the first real run (aggregate only)

Date of run: 2026-10-20. Tool: nepali-resource-audit 0.1.0. **Offline run**: no link check and no licence lookup
were possible in the environment used, so nothing below says whether any link is alive or what any resource's
licence actually is.

Inputs (README of each repository, shallow clone, commit in parentheses):

| list | commit | date of commit |
|---|---|---|
| pemagrg1/Nepali-Datasets | af3ea9b | 2026-09-07 |
| theranjitraut/Nepali-Datasets-Collection | 01df1e8 | 2026-08-11 |
| IOST-ASCOL/nepali-datasets | 8b62a18 | 2026-09-05 |
| ghimiresunil/Curated-List-of-Nepali-NLP-Resources | 2fbefa8 | 2022-12-22 |

Only aggregate numbers are published here; the per-resource catalogue is not redistributed (reproduce it with the
command in the README). The lists are the work of their authors.

## Numbers

- 965 link mentions → **575 unique resources** after canonicalisation (GitHub/Hugging Face/Kaggle/arXiv/DOI forms merged).
- **157** resources appear in two or more lists, **44** in three or more, **18** in all four.
- **0 of 575** have a licence statement (CC-*, MIT, Apache, GPL, ODbL, public domain, …) on their own entry line.
  I checked this independently with `grep`: the only "licen[cs]e" hits on lines containing links concern licence
  *plates* and driving-licence question datasets.
- `pemagrg1/Nepali-Datasets` marks 124 entries with "✓" (its README calls the collection "thoroughly verified");
  what was verified is not stated in the README, and this tool cannot confirm it offline.
- `theranjitraut/Nepali-Datasets-Collection` repeats 151 of its 525 link mentions within the same file (e.g. the
  same dataset listed under several headings), which is how a 2,672-line README ends up with 374 unique resources.

| list | mentions | unique | only in this list |
|---|---|---|---|
| pemagrg1 | 142 | 132 | 2 |
| theranjitraut | 525 | 374 | 220 |
| IOST-ASCOL | 91 | 88 | 37 |
| ghimiresunil | 207 | 200 | 159 |

Pairwise overlap (unique resources shared): pemagrg1 & theranjitraut 130; theranjitraut & IOST-ASCOL 48;
theranjitraut & ghimiresunil 38; IOST-ASCOL & ghimiresunil 33; pemagrg1 & IOST-ASCOL 25; pemagrg1 & ghimiresunil 25.

## What this does and does not show
- It shows heavy overlap and a lack of per-entry licence information *in these README files*. A licence may exist on
  the linked resource itself; the lists just do not say.
- Canonicalisation is conservative (e.g. GitHub URLs are merged at repository level), so the true overlap could
  differ slightly in either direction. The extraction is regex-based over Markdown; unusual formatting can be missed.
- No claim is made about the quality, legality or reliability of any listed resource.
- Suggested next steps for the maintainers of such lists (a suggestion, not a finding): add a licence column, run
  `nra audit --check-links --lookup-licenses` periodically in CI, and merge duplicate entries.
