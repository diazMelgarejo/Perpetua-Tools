<!-- markdownlint-disable MD013 -->
# Perpetua-Tools endpoint hardening checklists

Layer 1 = `src/utils/endpoint_policy_core.py` + `config/endpoint-policy-contract.yml`
Layer 2 = `src/utils/ssrf_pinned_adapter.py` (this drop-in)
Layer 3 = IMDS / egress (operator, not Python)

Fail closed. No UI toggle. Env override only, reviewed.

---

## PR-P1 — Pre-flight validator

- [ ] Scheme allowlist is `https` (optional `http` only if a test proves a vendor still needs it)
- [ ] Userinfo (`user:pass@host`) rejected
- [ ] Control chars (`CR`/`LF`/`NUL`) rejected
- [ ] `socket.getaddrinfo` checks **every** A/AAAA record; any blocked IP fails the whole name
- [ ] Denylist includes at least:
  - [ ] `0.0.0.0/8`, `127.0.0.0/8`, `::1/128`
  - [ ] RFC1918
  - [ ] CGNAT `100.64.0.0/10`
  - [ ] Link-local `169.254.0.0/16` (covers `169.254.169.254` and ECS `169.254.170.2`)
  - [ ] IPv6 link-local `fe80::/10`
  - [ ] AWS IPv6 IMDS `fd00:ec2::254`
  - [ ] Multicast `224.0.0.0/4`, `ff00::/8`
  - [ ] ULA `fc00::/7`
  - [ ] IPv4-mapped IPv6 unwrapped (`::ffff:169.254.169.254`)
- [ ] Octal / hex / dword / mixed encodings canonicalize before compare
- [ ] NXDOMAIN and empty `getaddrinfo` fail closed
- [ ] Override is env-only (existing PT flag), not a dashboard control
- [ ] Docstring states: this module does **not** stop DNS rebinding or redirects
- [ ] Property tests cover encoding classes + each denied range
- [ ] `test_verify_model_endpoint_policy_parity.py` still passes against orama contract

## PR-P2 — Pinned `requests` adapter

- [ ] `SSRFPinnedHTTPAdapter` lives in `src/utils/ssrf_pinned_adapter.py`
- [ ] Hooks `endpoint_policy_core` checkers when importable (`hook_endpoint_policy`)
- [ ] Resolve once → validate all IPs → `create_connection((pinned_ip, port))`
- [ ] TLS `server_hostname` / `assert_hostname` stay the original hostname (SNI + cert)
- [ ] `Host` header is the original hostname
- [ ] `getpeername()` re-checked after connect (MLflow-style belt)
- [ ] `send()` forces no proxy and does not honor caller `allow_redirects=True`
- [ ] `ssrf_request()` follows Location only after `urljoin` + re-validate; cap default 3
- [ ] 301/302/303 convert method to GET and drop body
- [ ] Tests (mocked DNS/socket, no live IMDS):
  - [ ] Public name with mixed public+private A/AAAA → denied
  - [ ] Redirect to `169.254.169.254` → `AddressDenied` / `RedirectDenied`
  - [ ] Rebinding sim: check-time public, connect-time private → denied
  - [ ] Userinfo URL → `SSRFPolicyError`
  - [ ] Allowlisted vendor host (`api.perplexity.ai`, `api.x.ai`) still works with pin+SNI

## PR-P3 — Wire every user-URL client

Mount the adapter or call `ssrf_request` in:

- [ ] `orchestrator/perplexity_client.py` (only if it fetches caller URLs; vendor API host can stay allowlisted)
- [ ] `orchestrator/gbrain_search.py`
- [ ] `orchestrator/autoresearch_bridge.py`
- [ ] `orchestrator/orama_mcp_client.py`
- [x] `orchestrator/connectivity.py`
- [ ] `src/utils/model_endpoint_url.py` consumers
- [ ] Any webhook / `fetch_url` / OpenClaw tool path that takes a string URL
- [ ] Grep clean: no new raw `requests.get/post` or `httpx.get` on untrusted URLs
- [ ] Audit log: host, resolved IPs, hop count, deny reason
- [x] Fixed vendor allowlist (Perplexity, xAI, OpenRouter) documented in `endpoint-policy-contract.yml`

## Operator / IMDS (docs only this pass)

- [ ] AWS: `HttpTokens=required` (IMDSv2), hop limit `1` (or `2` only if a container must read IMDS)
- [ ] Egress drop: `169.254.169.254/32`, `169.254.170.2/32`, `169.254.0.0/16`, `fd00:ec2::254/128`
- [ ] Prefer IRSA / Workload Identity so metadata credentials are low-value
- [ ] Optional later: Stripe Smokescreen in front of arbitrary-URL fetchers
- [ ] Jobs that fetch **arbitrary user URLs** require HITL `approval_token` (Amplifier Principle)

## Do not do

- [ ] Do not add `dssrf` or archived `safeurl-python`
- [ ] Do not ship SSRF protection disabled-by-default
- [ ] Do not treat Layer 1 as sufficient
- [ ] Do not send Flash/Grok jobs through a different unfiltered HTTP stack
- [ ] Do not mix this PR with the Grok 4.6 / Gemini 3.7 routing PRs
