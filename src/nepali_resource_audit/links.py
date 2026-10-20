"""Optional network features: link health checks and licence lookup. Both are opt-in, rate-limited,
and report *unverifiable* (blocked / login / rate-limited) separately from *dead*."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlsplit

from .urls import lookup_target

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
    if status in UNVERIFIABLE:
        return "unverifiable"
    if status >= 500:
        return "server-error"
    return "other"


def check_url(url: str, timeout: float = 10.0) -> dict:
    """HEAD, falling back to GET when the server rejects HEAD. Follows redirects."""
    result = {"url": url, "status": None, "state": "error", "final_url": None, "error": None,
              "checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                result.update(status=resp.status, final_url=resp.geturl(), error=None)
        except urllib.error.HTTPError as e:
            result.update(status=e.code, final_url=url, error=None)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            result.update(status=None, error=str(getattr(e, "reason", e))[:200])
            break
        if method == "HEAD" and result["status"] in (403, 405, 501):
            continue
        break
    result["state"] = _classify(result["status"], result["error"])
    return result


def check_links(urls: list[str], *, timeout: float = 10.0, workers: int = 8,
                per_host_delay: float = 0.5,
                checker: Callable[[str, float], dict] = check_url) -> dict[str, dict]:
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
        return checker(u, timeout)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(zip(urls, ex.map(one, urls), strict=True))


def fetch_json(url: str, timeout: float = 10.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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
