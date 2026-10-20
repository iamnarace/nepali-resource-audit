"""Combine mentions from several lists into a de-duplicated catalogue and summary statistics."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from .extract import Mention
from .urls import classify


def build_catalogue(mentions: list[Mention]) -> list[dict]:
    by: dict[str, list[Mention]] = defaultdict(list)
    for m in mentions:
        by[m.canonical].append(m)
    entries = []
    for canon, ms in sorted(by.items()):
        names = [n for n, _ in Counter(m.name for m in ms if m.name).most_common(3)]
        entries.append({
            "id": canon,
            "kind": classify(canon),
            "url": ms[0].url,
            "names": names,
            "sources": sorted({m.source for m in ms}),
            "sections": sorted({m.section for m in ms if m.section})[:5],
            "license_hints": sorted({h for m in ms for h in m.license_hints}),
            "claimed_verified_by": sorted({m.source for m in ms if m.verified_mark}),
        })
    return entries


def summarize(mentions: list[Mention], entries: list[dict], sources: list[str]) -> dict:
    per_source = {}
    for s in sources:
        ms = [m for m in mentions if m.source == s]
        uniq = {m.canonical for m in ms}
        es = [e for e in entries if s in e["sources"]]
        per_source[s] = {
            "mentions": len(ms),
            "unique_resources": len(uniq),
            "repeated_within_source": len(ms) - len(uniq),
            "with_license_hint": sum(1 for e in es if e["license_hints"]),
            "claimed_verified": sum(1 for e in es if s in e["claimed_verified_by"]),
            "only_in_this_source": sum(1 for e in es if e["sources"] == [s]),
        }
    overlap = {}
    for a, b in combinations(sources, 2):
        overlap[f"{a} & {b}"] = sum(1 for e in entries if a in e["sources"] and b in e["sources"])
    multiplicity = Counter(len(e["sources"]) for e in entries)
    return {
        "sources": sources,
        "total_mentions": len(mentions),
        "unique_resources": len(entries),
        "in_2_or_more_sources": sum(c for k, c in multiplicity.items() if k >= 2),
        "in_3_or_more_sources": sum(c for k, c in multiplicity.items() if k >= 3),
        "in_all_sources": multiplicity.get(len(sources), 0) if len(sources) > 1 else 0,
        "per_source": per_source,
        "pairwise_overlap": overlap,
        "by_kind": dict(Counter(e["kind"] for e in entries).most_common()),
        "with_any_license_hint": sum(1 for e in entries if e["license_hints"]),
        "without_license_hint": sum(1 for e in entries if not e["license_hints"]),
        "conflicting_license_hints": [
            e["id"] for e in entries if len(e["license_hints"]) > 1],
    }


def apply_link_results(entries: list[dict], results: dict[str, dict]) -> None:
    for e in entries:
        r = results.get(e["url"])
        if r:
            e["link"] = {k: r[k] for k in ("state", "status", "final_url", "error", "checked")}


def apply_license_lookups(entries: list[dict], lookups: dict[str, dict | None]) -> None:
    for e in entries:
        v = lookups.get(e["id"])
        if v is not None:
            e["declared_license"] = v


def link_summary(entries: list[dict]) -> dict:
    checked = [e for e in entries if "link" in e]
    states = Counter(e["link"]["state"] for e in checked)
    return {"checked": len(checked), "states": dict(states)}
