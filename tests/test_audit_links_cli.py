import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from nepali_resource_audit.audit import (
    apply_license_lookups,
    apply_link_results,
    build_catalogue,
    link_summary,
    summarize,
)
from nepali_resource_audit.cli import main
from nepali_resource_audit.extract import extract_file, extract_markdown
from nepali_resource_audit.links import check_links, check_url, lookup_license
from nepali_resource_audit.site import write_site

FIX = Path(__file__).parent / "fixtures"


def catalogue():
    ms = extract_file(FIX / "list_a.md", "A") + extract_file(FIX / "list_b.md", "B")
    entries = build_catalogue(ms)
    return ms, entries, summarize(ms, entries, ["A", "B"])


def test_summary_numbers_match_hand_count():
    _, _, s = catalogue()
    assert (s["total_mentions"], s["unique_resources"]) == (9, 5)
    assert s["in_2_or_more_sources"] == 4 and s["in_all_sources"] == 4 and s["in_3_or_more_sources"] == 0
    assert s["pairwise_overlap"] == {"A & B": 4}
    assert s["per_source"]["B"]["only_in_this_source"] == 1
    assert s["per_source"]["A"]["claimed_verified"] == 2 and s["per_source"]["B"]["claimed_verified"] == 0
    assert s["with_any_license_hint"] == 2 and s["without_license_hint"] == 3
    assert s["conflicting_license_hints"] == ["github.com/exampleorg/speech-set"]
    assert s["by_kind"]["github-repo"] == 1


def test_repeats_within_one_list_are_counted():
    ms = extract_markdown("- [a](https://example.org/x)\n- [b](https://example.org/x/)\n", "S")
    s = summarize(ms, build_catalogue(ms), ["S"])
    assert s["per_source"]["S"]["repeated_within_source"] == 1


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):  # noqa: N802
        self._respond(False)

    def do_GET(self):  # noqa: N802
        self._respond(True)

    def _respond(self, is_get):
        code = {"/ok": 200, "/gone": 404, "/blocked": 403, "/boom": 500, "/redir": 302,
                "/nohead": 200 if is_get else 405}.get(self.path, 404)
        self.send_response(code)
        if code == 302:
            self.send_header("Location", "/ok")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def test_check_url_states(server):
    states = {p: check_url(server + p, timeout=3, allow_private=True)["state"]
              for p in ("/ok", "/gone", "/blocked", "/boom", "/redir", "/nohead")}
    assert states == {"/ok": "ok", "/gone": "dead", "/blocked": "unverifiable", "/boom": "server-error",
                      "/redir": "ok", "/nohead": "ok"}
    assert check_url("http://127.0.0.1:1/x", timeout=2, allow_private=True)["state"] == "error"


def test_blocked_is_never_reported_as_dead(server):
    r = check_links([server + "/blocked", server + "/gone"], per_host_delay=0, workers=2, allow_private=True)
    assert r[server + "/blocked"]["state"] == "unverifiable" and r[server + "/gone"]["state"] == "dead"


def test_check_links_rate_limits_per_host(server):
    t = time.monotonic()
    check_links([server + "/ok", server + "/gone", server + "/blocked"],
                per_host_delay=0.2, workers=3, allow_private=True)
    assert time.monotonic() - t >= 0.35


def test_license_lookup_with_fake_fetch():
    gh = lookup_license("github.com/a/b", fetch=lambda u: {"license": {"spdx_id": "MIT"}})
    assert gh == {"value": "MIT", "source": "https://api.github.com/repos/a/b", "state": "declared"}
    assert lookup_license("github.com/a/b", fetch=lambda u: {"license": None})["state"] == "none-declared"
    noassert = lookup_license("github.com/a/b", fetch=lambda u: {"license": {"spdx_id": "NOASSERTION"}})
    assert noassert["state"] == "none-declared"
    hf = lookup_license("huggingface.co/datasets/o/n", fetch=lambda u: {"cardData": {"license": ["cc-by-4.0"]}})
    assert hf["value"] == "cc-by-4.0" and "/api/datasets/o/n" in hf["source"]
    assert lookup_license("github.com/a/b", fetch=lambda u: None)["state"] == "lookup-failed"
    assert lookup_license("kaggle.com/datasets/a/b") is None


def test_apply_results_and_summary():
    _, entries, _ = catalogue()
    urls = {e["url"]: {"state": "dead", "status": 404, "final_url": e["url"], "error": None, "checked": "t"}
            for e in entries}
    apply_link_results(entries, urls)
    assert link_summary(entries) == {"checked": 5, "states": {"dead": 5}}
    apply_license_lookups(entries, {entries[0]["id"]: {"value": "MIT", "source": "s", "state": "declared"}})
    assert sum("declared_license" in e for e in entries) == 1


def test_cli_end_to_end_with_site(tmp_path):
    out = tmp_path / "o"
    rc = main(["audit", "--source", f"A={FIX / 'list_a.md'}", "--source", f"B={FIX / 'list_b.md'}",
               "--out", str(out), "--site", "--generated", "2026-01-01"])
    assert rc == 0
    cat = json.loads((out / "catalogue.json").read_text(encoding="utf-8"))
    assert cat["summary"]["unique_resources"] == 5
    assert "Link check run: no" in (out / "report.md").read_text(encoding="utf-8")
    html = (out / "site" / "index.html").read_text(encoding="utf-8")
    assert "Nepali resource audit" in html and "exampleorg/news-corpus" in html
    assert main(["site", str(out / "catalogue.json"), "--out", str(tmp_path / "s2")]) == 0
    assert main(["audit", "--source", "bad", "--out", str(out)]) == 2
    assert main(["audit", "--source", "A=/nonexistent.md", "--out", str(out)]) == 2


def test_cli_live_check_flag_against_local_server(tmp_path, server):
    md = tmp_path / "l.md"
    md.write_text(f"- [ok]({server}/ok)\n- [gone]({server}/gone)\n- [blocked]({server}/blocked)\n",
                  encoding="utf-8")
    out = tmp_path / "o"
    assert main(["audit", "--source", f"L={md}", "--out", str(out), "--check-links", "--workers", "2",
                 "--allow-private-hosts"]) == 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Link check run: yes" in report and "| dead | 1 |" in report and "| unverifiable | 1 |" in report


def test_site_embeds_data_safely_and_is_self_contained(tmp_path):
    hostile = "</scr" + "ipt><b>x</b>"  # would end the data block early if not escaped
    entry = {"id": "x", "kind": "other", "url": "https://example.org/" + hostile, "names": [hostile],
             "sources": ["A"], "sections": [], "license_hints": [], "claimed_verified_by": []}
    summary = {"sources": ["A"], "unique_resources": 1, "in_2_or_more_sources": 0,
               "without_license_hint": 1, "by_kind": {"other": 1}}
    html = write_site(tmp_path, [entry], summary, {"generated": "d"}).read_text(encoding="utf-8")
    assert html.count("</scr" + "ipt>") == 2  # only the template's own two closing tags
    assert "innerHTML" not in html
    assert "https://" not in html.split('<script id="data"')[0]  # no external assets in head/body
