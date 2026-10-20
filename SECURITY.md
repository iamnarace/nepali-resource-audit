# Security policy

## Reporting a vulnerability
Use GitHub's private vulnerability reporting (Security tab → "Report a vulnerability"). If unavailable, open an issue
asking for a private contact channel **without** exploit details. Volunteer-maintained; no guaranteed response time.

## Threat model in brief
- Input Markdown lists are **untrusted**: URLs and names inside them can be hostile.
- Network access happens only with `--check-links` / `--lookup-licenses`. Link checking applies a safety policy
  (http(s) only, ports 80/443, public addresses only, validated redirects) that prevents a hostile list from making the tool
  probe loopback, private networks or cloud-metadata endpoints. `--allow-private-hosts` disables the address/port policy.
  Known limitation: DNS-rebinding race and proxy-side name resolution (see README).
- The static site inserts list data with `textContent` only, escapes the embedded JSON, and carries a Content-Security-Policy
  (`default-src 'none'`, inline script/style only). Links use `rel="noopener noreferrer"`.
- Licence lookups use fixed hosts (api.github.com, huggingface.co); path segments are validated.
- No credentials are read or stored. (GitHub API calls are unauthenticated.)

## Automated checks in CI
`ruff`, `pytest -W error` (includes SSRF policy tests), `bandit -r src`, `pip-audit` (dev dependencies; no runtime
dependencies), GitHub secret scanning + push protection, Dependabot security updates (+ weekly update PRs for GitHub
Actions and dev tools). These reduce risk; they do not prove absence of vulnerabilities.
