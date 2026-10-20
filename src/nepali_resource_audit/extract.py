"""Extract resource entries from Markdown lists (READMEs of community catalogues)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .urls import canonicalize

MD_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)[^)]*\)")
BARE_URL = re.compile(r"https?://[^\s)\]>\"'<]+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
VERIFIED_MARK = re.compile("[✓✔✅]")
LICENSE_PATTERNS = [
    (re.compile(r"\bCC0(?:[- ]1\.0)?\b", re.I), "CC0-1.0"),
    (re.compile(r"\bCC[- ]BY[- ]NC[- ]SA(?:[- ]\d\.\d)?\b", re.I), "CC-BY-NC-SA"),
    (re.compile(r"\bCC[- ]BY[- ]NC(?:[- ]\d\.\d)?\b", re.I), "CC-BY-NC"),
    (re.compile(r"\bCC[- ]BY[- ]ND(?:[- ]\d\.\d)?\b", re.I), "CC-BY-ND"),
    (re.compile(r"\bCC[- ]BY[- ]SA(?:[- ]\d\.\d)?\b", re.I), "CC-BY-SA"),
    (re.compile(r"\bCC[- ]BY(?:[- ]\d\.\d)?\b", re.I), "CC-BY"),
    (re.compile(r"\bApache(?:[- ]License)?(?:[- ]2(?:\.0)?)?\b", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT(?: License)?\b"), "MIT"),
    (re.compile(r"\bGPL(?:[- ]?v?[23])?\b", re.I), "GPL"),
    (re.compile(r"\bODbL\b|Open Database License", re.I), "ODbL"),
    (re.compile(r"\bpublic domain\b", re.I), "public-domain"),
    (re.compile(r"\bOpen Data Commons\b|\bODC-", re.I), "ODC"),
]
_SKIP_SCHEMES = ("badge", "shields.io")


@dataclass
class Mention:
    source: str
    url: str
    canonical: str
    name: str
    section: str
    line: int
    license_hints: list[str] = field(default_factory=list)
    verified_mark: bool = False


def license_hints(text: str) -> list[str]:
    """Licence names mentioned in ``text`` (the list entry's own line). Hints are the *list's*
    claim, not verified licences."""
    # Remove URLs first so e.g. a repository called 'mit-...' is not read as a licence.
    clean = BARE_URL.sub(" ", text)
    seen: list[str] = []
    for rx, name in LICENSE_PATTERNS:
        if rx.search(clean):
            seen.append(name)
    # Keep only the most specific name: "CC-BY-NC-SA" also matches the shorter CC-BY-NC / CC-BY patterns.
    seen = [a for a in seen if not any(b != a and b.startswith(a + "-") for b in seen)]
    return seen


def _plain(s: str) -> str:
    s = MD_LINK.sub(lambda m: m.group(1), s)
    return re.sub(r"[*_`]|<[^>]+>", "", s).strip(" -|:✓✔✅")


def _entry_name(line: str, link_text: str) -> str:
    stripped = line.strip()
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells and _plain(cells[0]):
            return _plain(cells[0])[:120]
    m = re.match(r"^\s*(?:[-*+]|\d+\.)\s+\*\*(.+?)\*\*", line)
    if m:
        return _plain(m.group(1))[:120]
    m = re.match(r"^\s*(?:[-*+]|\d+\.)\s+\[([^\]]+)\]\(", line)
    if m:
        return _plain(m.group(1))[:120]
    return (link_text or _plain(line))[:120]


def extract_markdown(text: str, source: str) -> list[Mention]:
    out: list[Mention] = []
    section = ""
    in_code = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        h = HEADING.match(line)
        if h:
            section = _plain(h.group(2))
            continue
        urls: list[tuple[str, str]] = [(m.group(2), m.group(1)) for m in MD_LINK.finditer(line)]
        rest = MD_LINK.sub(" ", line)
        urls += [(u, "") for u in BARE_URL.findall(rest)]
        urls = [(u, t) for u, t in urls if not any(s in u for s in _SKIP_SCHEMES)]
        if not urls:
            continue
        hints = license_hints(line)
        mark = bool(VERIFIED_MARK.search(line))
        for url, link_text in urls:
            url = url.rstrip(".,);>*'\"")
            out.append(Mention(source, url, canonicalize(url), _entry_name(line, link_text),
                               section, n, hints, mark))
    return out


def extract_file(path: str | Path, source: str | None = None) -> list[Mention]:
    p = Path(path)
    return extract_markdown(p.read_text(encoding="utf-8"), source or p.stem)
