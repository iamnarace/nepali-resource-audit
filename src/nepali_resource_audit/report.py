"""Markdown report from a catalogue summary."""

from __future__ import annotations

import json

from .audit import link_summary

NOTE = (
    "> Counts describe the *lists as they were read*. License hints are what the list itself says on the "
    "entry's line (often nothing) — they are not verified licences. 'Claimed verified' counts check-marks "
    "(✓/✅) in the list; this tool does not confirm them unless a link check or licence lookup was run, "
    "which this report states explicitly.\n"
)


def markdown(summary: dict, entries: list[dict], meta: dict) -> str:
    L = ["# Resource list audit", "", NOTE,
         f"- Tool: nepali-resource-audit {meta.get('version')}",
         f"- Generated: {meta.get('generated')}",
         f"- Inputs: {json.dumps(meta.get('inputs', {}), ensure_ascii=False)}",
         f"- Link check run: {'yes' if meta.get('link_check') else 'no'}; "
         f"licence lookup run: {'yes' if meta.get('license_lookup') else 'no'}", "",
         "## Headline numbers", "",
         f"- Total link mentions: **{summary['total_mentions']}**",
         f"- Unique resources after canonicalisation: **{summary['unique_resources']}**",
         f"- Appear in 2+ lists: **{summary['in_2_or_more_sources']}**; in 3+: "
         f"**{summary['in_3_or_more_sources']}**; in all {len(summary['sources'])}: "
         f"**{summary['in_all_sources']}**",
         f"- With any licence hint in the list: **{summary['with_any_license_hint']}**; "
         f"without: **{summary['without_license_hint']}**", "",
         "## Per list", "",
         "| list | mentions | unique | repeated inside list | licence hint | claimed ✓ | only in this list |",
         "|---|---|---|---|---|---|---|"]
    for s, d in summary["per_source"].items():
        L.append(f"| {s} | {d['mentions']} | {d['unique_resources']} | {d['repeated_within_source']} | "
                 f"{d['with_license_hint']} | {d['claimed_verified']} | {d['only_in_this_source']} |")
    L += ["", "## Pairwise overlap (unique resources in both lists)", "", "| pair | shared |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in summary["pairwise_overlap"].items()]
    L += ["", "## Resource kinds", "", "| kind | count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in summary["by_kind"].items()]
    if summary["conflicting_license_hints"]:
        L += ["", f"## Entries whose lists give more than one licence hint "
                  f"({len(summary['conflicting_license_hints'])})", "",
              "Check each by hand; the hint may belong to a neighbouring link on the same line."]
    ls = link_summary(entries)
    if ls["checked"]:
        L += ["", "## Link health (live check)", "", f"Checked {ls['checked']} URLs.", "",
              "| state | count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(ls["states"].items())]
        L += ["", "`unverifiable` = the server refused automated access (401/403/405/429); this does NOT mean "
                  "the link is dead. `dead` = HTTP 404/410. `blocked-by-policy` = refused by the safety policy "
                  "(non-http(s), non-public address, unusual port, or unsafe redirect); it was NOT requested."]
    declared = [e for e in entries if "declared_license" in e]
    if declared:
        from collections import Counter
        c = Counter((e["declared_license"].get("value") or e["declared_license"]["state"])
                    for e in declared)
        L += ["", "## Declared licences (host metadata)", "", f"Looked up {len(declared)} resources.", "",
              "| declared licence / state | count |", "|---|---|"] + [
            f"| {k} | {v} |" for k, v in c.most_common()]
        L += ["", "Declared by the host's metadata; always confirm on the resource page before reuse."]
    L += [""]
    return "\n".join(L)
