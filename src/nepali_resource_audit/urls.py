"""URL canonicalisation so the same resource linked in different ways is counted once."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit

_KAGGLE_RESERVED = {"datasets", "models", "competitions", "c", "code", "discussions", "learn",
                    "organizations", "docs", "benchmarks"}
_PAPER_HOSTS = ("arxiv.org", "aclanthology.org", "aclweb.org", "ieeexplore.ieee.org", "doi.org",
                "dx.doi.org", "link.springer.com", "researchgate.net", "semanticscholar.org",
                "papers.nips.cc", "openreview.net", "dl.acm.org", "sciencedirect.com", "mdpi.com",
                "ieee-dataport.org", "zenodo.org", "paperswithcode.com", "proceedings.mlr.press")


def canonicalize(url: str) -> str:
    """Return a canonical key for ``url`` (not necessarily a fetchable URL)."""
    url = url.strip().rstrip(".,);>*'\"")
    p = urlsplit(url)
    host = p.netloc.lower().removeprefix("www.")
    segs = [s for s in p.path.split("/") if s]
    if host == "github.com" and len(segs) >= 2:
        return f"github.com/{segs[0].lower()}/{segs[1].lower().removesuffix('.git')}"
    if host in ("huggingface.co", "hf.co") and segs:
        if segs[0] in ("datasets", "spaces") and len(segs) >= 3:
            return f"huggingface.co/{segs[0]}/{segs[1].lower()}/{segs[2].lower()}"
        if segs[0] not in ("datasets", "spaces", "docs", "blog", "papers") and len(segs) >= 2:
            return f"huggingface.co/{segs[0].lower()}/{segs[1].lower()}"
    if host == "kaggle.com" and segs:
        if segs[0] == "datasets" and len(segs) >= 3:
            return f"kaggle.com/datasets/{segs[1].lower()}/{segs[2].lower()}"
        if segs[0] not in _KAGGLE_RESERVED and len(segs) == 2:
            return f"kaggle.com/datasets/{segs[0].lower()}/{segs[1].lower()}"
    if host == "arxiv.org" and len(segs) >= 2 and segs[0] in ("abs", "pdf", "html"):
        ident = "/".join(segs[1:]).removesuffix(".pdf")
        ident = re.sub(r"v\d+$", "", ident)
        return f"arxiv.org/abs/{ident}"
    if host == "dx.doi.org":
        host = "doi.org"
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    path = "/".join(segs)
    out = f"{host}/{path}" if path else host
    if host == "doi.org":
        out = out.lower()
    return out + (f"?{urlencode(query)}" if query else "")


def classify(canonical: str) -> str:
    host = canonical.split("/", 1)[0]
    if host == "github.com":
        return "github-repo"
    if host == "huggingface.co":
        if "/" not in canonical:
            return "other"
        return {"datasets": "huggingface-dataset", "spaces": "huggingface-space"}.get(
            canonical.split("/")[1], "huggingface-model")
    if host == "kaggle.com":
        return "kaggle-dataset" if "/datasets/" in canonical else "kaggle-other"
    if host == "drive.google.com":
        return "google-drive"
    if host == "openslr.org":
        return "openslr"
    if any(host == h or host.endswith("." + h) for h in _PAPER_HOSTS):
        return "paper-or-archive"
    return "other"


_SAFE_SEG = re.compile(r"^[A-Za-z0-9_.-]+$")


def _safe(*segs: str) -> bool:
    return all(_SAFE_SEG.match(x) and x not in (".", "..") for x in segs)


def lookup_target(canonical: str) -> tuple[str, str] | None:
    """(kind, id) for hosts whose licence can be looked up through a public API."""
    parts = canonical.split("/")
    if parts[0] == "github.com" and len(parts) == 3 and _safe(parts[1], parts[2]):
        return ("github", f"{parts[1]}/{parts[2]}")
    if parts[0] == "huggingface.co" and len(parts) > 1:
        if parts[1] == "datasets" and len(parts) == 4 and _safe(parts[2], parts[3]):
            return ("hf-dataset", f"{parts[2]}/{parts[3]}")
        if parts[1] not in ("spaces",) and len(parts) == 3 and _safe(parts[1], parts[2]):
            return ("hf-model", f"{parts[1]}/{parts[2]}")
    return None
