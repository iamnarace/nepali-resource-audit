# Contributing

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && python -W error -m pytest -q
```

## Most useful contributions
1. **Real-world list formats that break extraction.** Open an issue with a *small* anonymised Markdown snippet and
   what you expected. Add it as a fixture in `tests/fixtures/` (only content you may share).
2. **More licence patterns** in `extract.py` (`LICENSE_PATTERNS`), each with a positive and a false-positive test
   (e.g. "License plate" must not count as a licence).
3. **Canonicalisation rules** for more hosts in `urls.py`, with tests showing same-resource and different-resource pairs.
4. **Nepali-language documentation** (needs native-speaker review).

## Rules
- Core stays dependency-free (standard library only).
- Network code must be opt-in, rate-limited, and must never turn a refusal (401/403/429) into "dead".
- Anything inserted into the HTML site must go through `textContent`; add a test for hostile input.
- Do not commit scraped third-party list content; use invented fixtures.

## Good first issues (suggested)
- Support reference-style Markdown links (`[text][ref]`).
- `--github-token-env NAME` for higher GitHub API limits.
- Add a `nra diff old.json new.json` command.
- Parse a YAML front-matter licence column some lists may adopt.

## Reporting problems
GitHub issues: include the command, the (small) input that fails, and expected vs actual output. Do not include
tokens or private data.
