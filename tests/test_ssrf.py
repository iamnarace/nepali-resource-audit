"""Safety policy for link checking: lists are untrusted input."""

import urllib.request

import pytest

from nepali_resource_audit.cli import main
from nepali_resource_audit.links import (
    UrlBlocked,
    _opener,
    _SafeRedirects,
    check_links,
    check_target,
    check_url,
)
from nepali_resource_audit.site import write_site
from nepali_resource_audit.urls import lookup_target


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.org/x", "gopher://example.org/", "data:text/plain,hi", "javascript:alert(1)",
    "http://127.0.0.1/", "http://127.0.0.1:8080/", "http://[::1]/", "http://localhost/", "http://10.0.0.5/",
    "http://172.16.0.1/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/",
    "http://0.0.0.0/", "http://[::ffff:127.0.0.1]/", "http://[fd00::1]/", "http://100.64.0.1/",
    "http://8.8.8.8:22/", "http://8.8.8.8:6379/", "http:///nohost",
])
def test_unsafe_targets_blocked(url):
    with pytest.raises(UrlBlocked):
        check_target(url)


@pytest.mark.parametrize("url", ["http://8.8.8.8/", "https://1.1.1.1/", "http://8.8.8.8:80/", "https://8.8.8.8:443/x"])
def test_public_literals_allowed(url):
    check_target(url)  # IP literals need no DNS, so this runs offline


def test_allow_private_flag_disables_ip_policy_but_not_scheme_policy():
    check_target("http://127.0.0.1:8080/", allow_private=True)
    with pytest.raises(UrlBlocked):
        check_target("file:///etc/passwd", allow_private=True)


def test_check_url_reports_blocked_without_requesting():
    r = check_url("http://169.254.169.254/latest/meta-data/")
    assert r["state"] == "blocked-by-policy" and "non-public" in r["error"]
    assert check_url("file:///etc/passwd")["state"] == "blocked-by-policy"


def test_check_links_default_blocks_loopback():
    r = check_links(["http://127.0.0.1:9/x"], per_host_delay=0)
    assert r["http://127.0.0.1:9/x"]["state"] == "blocked-by-policy"


def test_redirect_to_private_address_is_refused():
    handler = _SafeRedirects(allow_private=False)
    req = urllib.request.Request("http://8.8.8.8/")
    with pytest.raises(UrlBlocked):
        handler.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data/")
    with pytest.raises(UrlBlocked):
        handler.redirect_request(req, None, 302, "Found", {}, "file:///etc/passwd")


def test_opener_has_no_file_or_ftp_handlers():
    names = {type(h).__name__ for h in _opener(False).handlers}
    assert not names & {"FileHandler", "FTPHandler", "DataHandler"}


@pytest.mark.parametrize("canonical", ["github.com/../x", "github.com/a/..", "github.com/a b/c", "github.com/a/b%2f",
                                       "huggingface.co/datasets/a/b?x=1", "huggingface.co/a#frag/b"])
def test_lookup_target_rejects_odd_path_segments(canonical):
    assert lookup_target(canonical) is None


def test_cli_blocks_private_links_by_default(tmp_path):
    md = tmp_path / "l.md"
    md.write_text("- [meta](http://169.254.169.254/latest/)\n- [local](http://localhost:8080/)\n", encoding="utf-8")
    out = tmp_path / "o"
    assert main(["audit", "--source", f"L={md}", "--out", str(out), "--check-links"]) == 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "| blocked-by-policy | 2 |" in report and "NOT requested" in report


def test_site_has_content_security_policy(tmp_path):
    summary = {"sources": ["A"], "unique_resources": 0, "in_2_or_more_sources": 0,
               "without_license_hint": 0, "by_kind": {}}
    html = write_site(tmp_path, [], summary, {"generated": "d"}).read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    assert 'name="referrer" content="no-referrer"' in html
