"""``nra`` command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .audit import apply_license_lookups, apply_link_results, build_catalogue, summarize
from .extract import extract_file
from .links import check_links, lookup_license
from .report import markdown
from .site import write_site


def _parse_sources(items: list[str]) -> list[tuple[str, Path]]:
    out = []
    for it in items:
        name, sep, path = it.partition("=")
        if not sep or not name or not path:
            raise ValueError(f"--source must look like NAME=PATH (got {it!r})")
        if not Path(path).is_file():
            raise ValueError(f"source file not found: {path}")
        out.append((name, Path(path)))
    if len({n for n, _ in out}) != len(out):
        raise ValueError("source names must be unique")
    return out


def _audit(a) -> int:
    srcs = _parse_sources(a.source)
    mentions = []
    for name, path in srcs:
        mentions += extract_file(path, name)
    names = [n for n, _ in srcs]
    entries = build_catalogue(mentions)
    meta = {"version": __version__,
            "generated": a.generated or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "inputs": {n: str(p.name) for n, p in srcs},
            "link_check": a.check_links, "license_lookup": a.lookup_licenses}
    if a.check_links:
        urls = [e["url"] for e in entries]
        print(f"checking {len(urls)} links (rate-limited)...", file=sys.stderr)
        apply_link_results(entries, check_links(urls, timeout=a.timeout, workers=a.workers,
                                                allow_private=a.allow_private_hosts))
    if a.lookup_licenses:
        print("looking up declared licences (GitHub / Hugging Face)...", file=sys.stderr)
        apply_license_lookups(entries, {e["id"]: lookup_license(e["id"]) for e in entries})
    summary = summarize(mentions, entries, names)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalogue.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "entries": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (out / "report.md").write_text(markdown(summary, entries, meta), encoding="utf-8")
    if a.site:
        write_site(out / "site", entries, summary, meta)
    print(f"{summary['total_mentions']} mentions -> {summary['unique_resources']} unique; "
          f"{summary['in_2_or_more_sources']} in 2+ lists; wrote {out}/report.md")
    return 0


def _site(a) -> int:
    data = json.loads(Path(a.catalogue).read_text(encoding="utf-8"))
    write_site(Path(a.out), data["entries"], data["summary"], data["meta"])
    print(f"wrote {a.out}/index.html")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nra", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("audit", help="audit one or more Markdown lists")
    a_.add_argument("--source", action="append", required=True, metavar="NAME=PATH")
    a_.add_argument("--out", required=True)
    a_.add_argument("--check-links", action="store_true", help="live HTTP check (opt-in, rate-limited)")
    a_.add_argument("--lookup-licenses", action="store_true",
                    help="query GitHub / Hugging Face APIs for declared licences (opt-in)")
    a_.add_argument("--allow-private-hosts", action="store_true",
                    help="DISABLE the safety policy: also request loopback/private/link-local hosts and any port "
                         "(only for lists you fully trust)")
    a_.add_argument("--timeout", type=float, default=10.0)
    a_.add_argument("--workers", type=int, default=8)
    a_.add_argument("--site", action="store_true", help="also write a static searchable site")
    a_.add_argument("--generated", help="override the date stamp (for reproducible output)")
    a_.set_defaults(fn=_audit)
    s = sub.add_parser("site", help="build the static site from catalogue.json")
    s.add_argument("catalogue")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=_site)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
