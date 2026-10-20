"""Optional network features: link health checks and licence lookup. Both are opt-in, rate-limited,
and report *unverifiable* (blocked / login / rate-limited) separately from *dead*."""

from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlsplit

from .urls import lookup_target


class UrlBlocked(Exception):
    """The URL was refused by the safety policy (not a network failure)."""


_ALLOWED_PORTS = {None, 80, 443}


def _addr_is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def check_target(url: str, allow_private: bool = False) -> None:
    """Raise :class:`UrlBlocked` unless ``url`` is a safe thing to request.

    Lists are untrusted input: a hostile list could point at ``http://169.254.169.254/`` (cloud metadata),
    ``http://localhost:6379/`` or an intranet host. Unless ``allow_private`` is set, only http(s) URLs on
    ports 80/443 whose host resolves exclusively to public addresses are allowed. The same check runs on
    every redirect hop. Limitation: the name is resolved here and again by the HTTP stack (DNS rebinding
    race), and a configured HTTP proxy resolves names itself; run the audit in an environment without
    access to sensitive internal services.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UrlBlocked(f"scheme {parts.scheme!r} is not allowed")
    host = parts.hostname
    if not host:
        raise UrlBlocked("URL has no host")
    if allow_private:
        return
    try:
        port = parts.port
    except ValueError as e:
        raise UrlBlocked("invalid port") from e
    if port not in _ALLOWED_PORTS:
        raise UrlBlocked(f"port {port} is not allowed (only 80/443)")
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)}
    except OSError as e:
        raise OSError(f"cannot resolve {host}: {e}") from e  # a network failure, not a policy block
    for a in addrs:
        if not _addr_is_public(a):
            raise UrlBlocked(f"{host} resolves to a non-public address ({a})")


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private: bool):
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_target(newurl, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(allow_private: bool) -> urllib.request.OpenerDirector:
    """An opener limited to http(s) (no file:, ftp:, data:) that re-validates each redirect."""
    opener = urllib.request.OpenerDirector()
    for h in (urllib.request.ProxyHandler(), urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
              urllib.request.HTTPDefaultErrorHandler(), _SafeRedirects(allow_private),
              urllib.request.HTTPErrorProcessor(), urllib.request.UnknownHandler()):
        opener.add_handler(h)
    return opener


UA = "nepali-resource-audit/0.1 (+https://github.com/iamnarace/nepali-resource-audit; link health check)"
UNVERIFIABLE = {401, 403, 405, 429, 451, 999}


def _classify(status: int | None, error: str | None) -> str:
    if error:
        return "error"
    if status is None:
        return "error"
    if 200 <= status < 300:
        return "ok"
    if status in (404, 410):
        return "dead"
    if status == -1:
        return "blocked-by-policy"
    if status in UNVERIFIABLE:
        return "unverifiable"
    if status >= 500:
        return "server-error"
    return "other"


def check_url(url: str, timeout: float = 10.0, allow_private: bool = False) -> dict:
    """HEAD, falling back to GET when the server rejects HEAD. Follows (validated) redirects."""
    result = {"url": url, "status": None, "state": "error", "final_url": None, "error": None,
              "checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        check_target(url, allow_private)
    except UrlBlocked as e:
        result.update(status=-1, error=str(e), state="blocked-by-policy")
        return result
    except OSError as e:
        result.update(error=str(e)[:200])
        return result
    opener = _opener(allow_private)
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            # Scheme/host/port are validated by check_target (and per redirect hop); opener is http(s) only.
            with opener.open(req, timeout=timeout) as resp:  # nosec B310
                result.update(status=resp.status, final_url=resp.geturl(), error=None)
        except urllib.error.HTTPError as e:
            result.update(status=e.code, final_url=url, error=None)
        except UrlBlocked as e:
            result.update(status=-1, error=f"redirect refused: {e}")
            break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, UrlBlocked):
                result.update(status=-1, error=f"redirect refused: {reason}")
            else:
                result.update(status=None, error=str(reason)[:200])
            break
        if method == "HEAD" and result["status"] in (403, 405, 501):
            continue
        break
    result["state"] = _classify(result["status"], result["error"])
    return result


def check_links(urls: list[str], *, timeout: float = 10.0, workers: int = 8,
                per_host_delay: float = 0.5, allow_private: bool = False,
                checker: Callable[..., dict] = check_url) -> dict[str, dict]:
    """Check many URLs concurrently with a minimum delay between requests to the same host."""
    last: dict[str, float] = {}
    lock = Lock()

    def one(u: str) -> dict:
        host = urlsplit(u).netloc
        with lock:
            wait = last.get(host, 0.0) + per_host_delay - time.monotonic()
            last[host] = max(time.monotonic(), last.get(host, 0.0) + per_host_delay)
        if wait > 0:
            time.sleep(wait)
        return checker(u, timeout, allow_private)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(zip(urls, ex.map(one, urls), strict=True))


def fetch_json(url: str, timeout: float = 10.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        # Fixed https hosts (api.github.com / huggingface.co) built in lookup_license; not user-supplied.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def lookup_license(canonical: str, fetch: Callable[[str], dict | None] = fetch_json) -> dict | None:
    """Declared licence from the host's own metadata (GitHub repo licence / Hugging Face card)."""
    target = lookup_target(canonical)
    if not target:
        return None
    kind, ident = target
    if kind == "github":
        url = f"https://api.github.com/repos/{ident}"
        data = fetch(url)
        lic = (data or {}).get("license") or {}
        value = lic.get("spdx_id") if data else None
    else:
        seg = "datasets" if kind == "hf-dataset" else "models"
        url = f"https://huggingface.co/api/{seg}/{ident}"
        data = fetch(url)
        card = (data or {}).get("cardData") or {}
        value = card.get("license")
        if isinstance(value, list):
            value = ",".join(map(str, value))
    if not data:
        return {"value": None, "source": url, "state": "lookup-failed"}
    if not value or value == "NOASSERTION":
        return {"value": None, "source": url, "state": "none-declared"}
    return {"value": str(value), "source": url, "state": "declared"}
