"""Provider policies: limits, rates and billing facts confirmed from official references.

One shared place, used by every agent in Perpetua-Tools and by orama-system through
PERPETUA_TOOLS_ROOT. A policy file under config/provider-policies/ names the provider's endpoint, the
NAMES of its credential variables (never values), its budget, an upper-bound rate, the HTTP codes that
stop a loop, the operator attestation it requires, and official references whose facts can be
re-verified live. Loading a policy never authorizes spend.

    python3 -m orchestrator.provider_limits verify wandb-inference
    python3 -m orchestrator.provider_limits status wandb-inference

Both the interactive CLI and the portal relay write the attestation through
``write_attestation_record``; ``revoke_attestation`` withdraws it and audits that. This module is
the authority the portal relays to: it makes no network call and knows nothing about a browser.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

POLICY_DIR = Path(__file__).resolve().parents[1] / "config" / "provider-policies"
_MAX_PAGE_BYTES = 2_000_000
_SECRET_SHAPE = re.compile(r"(sk-|Bearer\s|eyJ|[A-Za-z0-9_\-]{32,})")  # a value, not a variable name
_PAYMENT = re.compile(
    r"\b402\b|payment required|spending cap|exceeded your current|insufficient (?:credit|fund)", re.I
)
_RATE = re.compile(r"\b429\b|too many requests|rate.?limit|concurrency limit", re.I)


ATTEST_PHRASE = "I read the provider Billing page myself"
_AUDIT_FORBIDDEN = {"prompt", "answer", "api_key", "key", "token", "text", "stdout", "stderr", "body"}


class ProviderPolicyError(RuntimeError):
    """The policy is missing, malformed or unsafe. Callers must treat this as a refusal."""


def state_dir() -> Path:
    """The operator state directory: $OPENCLAW_STATE_DIR, else ~/.openclaw/state."""
    return Path(os.environ.get("OPENCLAW_STATE_DIR") or os.path.expanduser("~/.openclaw/state"))


def attestation_path(provider: str) -> Path:
    """Return the operator attestation file for the named provider."""
    return state_dir() / "provider-attestations" / f"{provider}.json"


def attestation_audit_path(provider: str) -> Path:
    """Return the append-only audit log of attestation and revocation events for the provider."""
    return state_dir() / "provider-attestations" / f"{provider}-audit.jsonl"


def spend_dir() -> Path:
    """Return the shared state directory for spend ledgers and audits."""
    return state_dir() / "spend"


# Free-text fields (except ts) are short identifiers only: no spaces or prose, so a prompt cannot be
# stored under outcome/seat/label/etc. Enum vocabularies for seat/outcome are not defined in-repo yet.
_AUDIT_ID_FIELDS = {"seat", "mode", "outcome", "provider", "policy_id", "label", "basis"}
_AUDIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_AUDIT_TEXT_FIELDS = {"ts"} | _AUDIT_ID_FIELDS
_AUDIT_SIZE_FIELDS = {"input_chars", "output_chars", "estimated_usd"}
_AUDIT_BOOL_FIELDS = {"estimated"}
_AUDIT_FIELDS = _AUDIT_TEXT_FIELDS | _AUDIT_SIZE_FIELDS | _AUDIT_BOOL_FIELDS


def append_audit(path: Path, row: Mapping[str, Any]) -> None:
    """Append one size-only audit row. Only the schema's fields are allowed, each with its own type, so a
    prompt, answer, key or raw output cannot be smuggled in under any key name, as nested values, or as
    free prose in an identifier field."""
    bad = sorted(set(row) & _AUDIT_FORBIDDEN)
    if bad:
        raise ValueError(f"audit rows store sizes only; refused field(s): {', '.join(bad)}")
    extra = sorted(set(row) - _AUDIT_FIELDS)
    if extra:
        raise ValueError(f"audit rows store sizes only; unknown field(s): {', '.join(extra)}")
    for name in _AUDIT_ID_FIELDS & set(row):
        value = row[name]
        if not isinstance(value, str) or _AUDIT_ID.fullmatch(value) is None:
            raise ValueError(f"{name} must be a short identifier (letters, digits, _.-; max 64)")
    for name in _AUDIT_BOOL_FIELDS & set(row):
        if not isinstance(row[name], bool):
            raise ValueError(f"{name} must be true or false")
    for name in _AUDIT_SIZE_FIELDS & set(row):
        _size(row[name], name)
    datetime.fromisoformat(str(row["ts"]))
    _size(row["estimated_usd"], "estimated_usd")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _audit_token(value: Any) -> str:
    """Reduce free text to the audit alphabet (letters, digits, _.-) so no prose is ever stored."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip(".-")[:64] or "unspecified"


def _attest_actor(value: Any, field: str) -> str:
    """The named person for an attestation event; a blank or non-text name is refused."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _as_aware(now: Any) -> datetime:
    """Return an aware datetime; a naive one is read as UTC, exactly as attestation_status reads it."""
    if not isinstance(now, datetime):
        raise ValueError("now must be a datetime")
    return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)


def _provider_id(provider: Any) -> str:
    """A provider id names a file, so it must be a short identifier and never a path."""
    if not isinstance(provider, str) or _AUDIT_ID.fullmatch(provider) is None:
        raise ValueError("provider must be a short identifier (letters, digits, _.-; max 64)")
    return provider


def _write_private_record(path: Path, text: str) -> None:
    """Write the record in one rename, created 0600: a reader sees the old file, the new one, or none."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _append_attestation_audit(provider: str, policy_id: Any, outcome: str, actor: str,
                              reason: Any, when: datetime) -> None:
    """Append one size-only audit row for an attestation event: identifiers only, never prose."""
    row: dict[str, Any] = {"ts": when.isoformat(), "provider": provider, "outcome": outcome,
                           "label": _audit_token(actor), "estimated_usd": 0.0}
    if policy_id:
        row["policy_id"] = _audit_token(policy_id)
    if reason:
        row["basis"] = _audit_token(reason)
    append_audit(attestation_audit_path(provider), row)


_PROHIBITED_PROOF_SOURCES = {"hold_to_confirm", "dialog_click", "client_checkbox"}
_VALID_AUTHORITY_PROOF_TYPES = {"webauthn_touch_id", "webauthn_security_key", "operator_attestation"}


def _verify_human_presence(presence_proof: Any, now: datetime) -> str:
    """Validate human presence proof, returning the confirmed proof type label.

    Strictly refuses automated attestation. Allowed proofs:
    1. Interactive terminal typing: exact match of ATTEST_PHRASE on an interactive terminal (_is_interactive()).
    2. AuthorityProof mapping: valid proof_type ('webauthn_touch_id', 'webauthn_security_key',
       'operator_attestation'), non-empty raw_proof, non-empty device_id, and unexpired expires_at.

    Prohibited sources ('hold_to_confirm', 'dialog_click', 'client_checkbox') and missing or
    non-interactive proofs are strictly refused.
    """
    if presence_proof is None or presence_proof == "":
        raise ValueError("refused: human presence proof required; automated attestation is refused")

    if isinstance(presence_proof, str):
        if not _is_interactive():
            raise ValueError("refused: interactive confirmation phrase requires an active interactive terminal")
        if presence_proof != ATTEST_PHRASE:
            raise ValueError("refused: the typed confirmation phrase did not match")
        return "interactive_terminal"

    if isinstance(presence_proof, Mapping):
        ptype = presence_proof.get("proof_type") or presence_proof.get("proofType")
        if not ptype or not isinstance(ptype, str):
            raise ValueError("refused: presence proof missing proof_type")
        if ptype in _PROHIBITED_PROOF_SOURCES:
            raise ValueError(f"refused: {ptype} is prohibited as authority proof")
        if ptype in ("interactive_phrase", "interactive_terminal"):
            if not _is_interactive():
                raise ValueError("refused: interactive confirmation phrase requires an active interactive terminal")
            phrase = presence_proof.get("phrase")
            if phrase != ATTEST_PHRASE:
                raise ValueError("refused: the typed confirmation phrase did not match")
            return "interactive_terminal"
        if ptype in _VALID_AUTHORITY_PROOF_TYPES:
            raw = presence_proof.get("raw_proof") or presence_proof.get("rawProof")
            dev = presence_proof.get("device_id") or presence_proof.get("deviceId")
            if not (isinstance(raw, str) and raw.strip()):
                raise ValueError("refused: authority proof requires non-empty raw_proof")
            if not (isinstance(dev, str) and dev.strip()):
                raise ValueError("refused: authority proof requires non-empty device_id")
            exp = presence_proof.get("expires_at") or presence_proof.get("expiresAt")
            if exp:
                try:
                    exp_dt = datetime.fromisoformat(str(exp))
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc) if exp_dt.tzinfo is None else exp_dt.astimezone(timezone.utc)
                    if exp_dt < now.astimezone(timezone.utc):
                        raise ValueError("refused: authority proof has expired")
                except ValueError as exc:
                    if "expired" in str(exc):
                        raise
                    raise ValueError("refused: invalid expires_at in authority proof") from exc
            return ptype
        raise ValueError(f"refused: unsupported presence proof type '{ptype}'")

    raise ValueError("refused: invalid presence proof structure")


def write_attestation_record(provider: str, attested_by: str, facts: Mapping[str, Any],
                             now: datetime, presence_proof: Mapping[str, Any] | str) -> Path:
    """Write the operator attestation for ``provider``, audit it, and return the record path.

    The one authority behind both the interactive CLI and a portal relay. It requires verified
    proof of human presence (interactive terminal confirmation or valid AuthorityProof); automated
    attestation without presence proof is strictly refused. Refuses unless the provider has a valid
    policy, the attestor is named, and every fact that policy requires is exactly ``True``; an unknown
    fact is refused too, so a caller cannot attest more than the policy asks. The record keeps the schema
    the CLI always wrote, is created 0600 through one rename (no reader and no crash ever sees a partial
    file), and is followed by one audit row.
    """
    when = _as_aware(now)
    proof_type = _verify_human_presence(presence_proof, when)
    policy = load_policy(provider)
    name = _provider_id(policy["provider"])
    who = _attest_actor(attested_by, "attested_by")
    if not isinstance(facts, Mapping):
        raise ValueError("facts must map the policy's attestation fields to True")
    required = list(policy["operator_attestation"]["fields"])
    refused = [f"{field} must be true" for field in required if facts.get(field) is not True]
    refused += [f"{field} is not a policy fact" for field in sorted(set(facts) - set(required))]
    if refused:
        raise ValueError("refused: " + "; ".join(refused))
    record: dict[str, Any] = {"provider": name, "attested_at": when.isoformat(), "attested_by": who}
    record.update(dict.fromkeys(required, True))
    path = attestation_path(name)
    prev_bytes: bytes | None = None
    try:
        prev_bytes = path.read_bytes()
    except FileNotFoundError:
        prev_bytes = None

    _write_private_record(path, json.dumps(record, indent=2) + "\n")
    try:
        _append_attestation_audit(name, policy.get("policy_id"), "attestation-written", who, "", when)
    except BaseException:
        if prev_bytes is None:
            path.unlink(missing_ok=True)
        else:
            try:
                _write_private_record(path, prev_bytes.decode("utf-8"))
            except BaseException:
                path.unlink(missing_ok=True)
        raise
    return path


def revoke_attestation(provider: str, revoked_by: str, reason: str, now: datetime) -> bool:
    """Remove ``provider``'s attestation, audit it, and leave attestation_status reporting missing.

    Revoking never loads the policy, so authority can always be withdrawn, even for a provider whose
    policy changed or was deleted. Removing a record that is not there is a clean no-op and is
    audited as ``attestation-revoke-missing``. Returns True when a record was removed. If audit
    recording fails, revocation remains fail-closed (unlinked) and the error is re-raised.
    """
    name = _provider_id(provider)
    who = _attest_actor(revoked_by, "revoked_by")
    when = _as_aware(now)
    removed = False
    try:
        attestation_path(name).unlink()
        removed = True
    except FileNotFoundError:
        pass
    outcome = "attestation-revoked" if removed else "attestation-revoke-missing"
    _append_attestation_audit(name, None, outcome, who, reason, when)
    return removed


def _finite_positive(value: Any) -> bool:
    """Accept finite positive numeric policy values, excluding booleans."""
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and value > 0
    )


def _size(value: Any, name: str) -> float:
    """Validate a finite nonnegative size and return it as a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite number >= 0")
    return float(value)


def _validate(policy: Mapping[str, Any]) -> None:
    """Reject malformed or unsafe provider policy fields before use."""
    def need(cond: bool, msg: str) -> None:
        """Raise a policy error when a required invariant is false."""
        if not cond:
            raise ProviderPolicyError(msg)

    try:
        need(policy.get("schema_version") == 1, "schema_version must be 1")
        need(isinstance(policy.get("provider"), str) and bool(policy["provider"]), "provider is required")
        need(str(policy["applicable_endpoint"]["base_url"]).startswith("https://"), "base_url must be https")
        for key, name in policy["key_env_vars"].items():
            need(isinstance(name, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is not None,
                 f"key_env_vars.{key} must be a variable name, not a value")
            need(not _SECRET_SHAPE.search(name) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,40}", name) is not None,
                 f"key_env_vars.{key} looks like a secret")
        rates = policy["rates_usd_per_million_tokens"]
        need(_finite_positive(rates["input"]) and _finite_positive(rates["output"]), "rates must be finite and > 0")
        budget = policy["budget"]
        need(budget["period"] in ("monthly", "daily"), "budget.period must be monthly or daily")
        need(_finite_positive(budget["operator_estimate_ceiling_usd"]), "budget ceiling must be > 0")
        need(_finite_positive(budget["provider_default_cap_usd_after_payg"]), "provider cap must be > 0")
        need(budget["operator_estimate_ceiling_usd"] < budget["provider_default_cap_usd_after_payg"],
             "the budget ceiling must stay below the provider cap")
        proj = policy["projection"]
        need(_finite_positive(proj["chars_per_token"]) and _finite_positive(proj["assumed_output_chars"]),
             "projection values must be finite and > 0")
        stops = policy["stop_on_http"]
        need(isinstance(stops, list) and bool(stops) and all(isinstance(c, int) and not isinstance(c, bool) for c in stops),
             "stop_on_http must be a non-empty list of integers")
        att = policy["operator_attestation"]
        need(att["required"] is True and isinstance(att["max_age_days"], int)
             and not isinstance(att["max_age_days"], bool) and att["max_age_days"] > 0,
             "operator_attestation needs required true and max_age_days > 0")
        need(isinstance(att["fields"], list) and bool(att["fields"]), "operator_attestation.fields is required")
        refs = policy["official_references"]
        need(isinstance(refs, list) and bool(refs), "official_references is required")
        for ref in refs:
            need(str(ref["url"]).startswith("https://"), "official reference urls must be https")
            need(isinstance(ref["facts"], list) and bool(ref["facts"]), "each reference needs facts")
            for fact in ref["facts"]:
                try:
                    re.compile(fact["expect"])
                except re.error as exc:
                    raise ProviderPolicyError(f"fact {fact.get('id')} has a bad pattern: {exc}") from exc
                need(isinstance(fact.get("sample"), str) and bool(fact["sample"]), f"fact {fact.get('id')} needs a sample")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ProviderPolicyError(f"malformed policy: {exc!r}") from exc


def load_policy(path_or_id: str | Path) -> dict:
    """Load and validate a policy by file path or by provider id. Fails closed."""
    candidate = Path(str(path_or_id))
    if not candidate.suffix:
        candidate = POLICY_DIR / f"{path_or_id}.json"
    if not candidate.is_file():
        raise ProviderPolicyError(f"no policy for {path_or_id!r}")
    try:
        policy = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderPolicyError(f"policy is not valid JSON: {exc}") from exc
    _validate(policy)
    return policy


def estimate_usd(policy: Mapping[str, Any], input_chars: Any, output_chars: Any) -> float:
    """Estimated dollars from sizes in characters at the policy's upper-bound rates."""
    per_token = policy["projection"]["chars_per_token"]
    rates = policy["rates_usd_per_million_tokens"]
    tin = _size(input_chars, "input_chars") / per_token
    tout = _size(output_chars, "output_chars") / per_token
    return tin / 1e6 * rates["input"] + tout / 1e6 * rates["output"]


def projected_usd(policy: Mapping[str, Any], input_chars: Any) -> float:
    """Cost to reserve before a request: its input plus the assumed reasoning-stream output."""
    return estimate_usd(policy, input_chars, policy["projection"]["assumed_output_chars"])


def attestation_status(policy: Mapping[str, Any], attestation: Any, now: datetime) -> dict:
    """ok only for a fresh attestation by the operator with every required field exactly True."""
    spec = policy["operator_attestation"]
    reasons: list[str] = []
    if not isinstance(attestation, Mapping) or not attestation:
        return {"ok": False, "reasons": ["attestation missing"] if attestation is None else ["attestation: provider missing"]}
    if attestation.get("provider") != policy["provider"]:
        reasons.append(f"attestation provider must be {policy['provider']}")
    if not (isinstance(attestation.get("attested_by"), str) and attestation["attested_by"].strip()):
        reasons.append("attested_by is required")
    for field in spec["fields"]:
        if attestation.get(field) is not True:
            reasons.append(f"{field} must be true")
    try:
        when = datetime.fromisoformat(str(attestation["attested_at"]))
        when = when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
        age_days = (now.astimezone(timezone.utc) - when).total_seconds() / 86400
        if age_days < -1 / 1440:
            reasons.append("attested_at is in the future")
        elif age_days > spec["max_age_days"]:
            reasons.append(f"attestation is stale ({age_days:.1f} days, limit {spec['max_age_days']})")
    except (KeyError, ValueError, TypeError):
        reasons.append("attested_at must be an ISO timestamp")
    return {"ok": not reasons, "reasons": reasons}


def classify_failure(policy: Mapping[str, Any], text: Any) -> str | None:
    """provider-payment-required, provider-rate-limited or None. Payment wins. Best effort on text."""
    if not isinstance(text, str) or not text:
        return None
    stops = set(policy["stop_on_http"])
    if 402 in stops and _PAYMENT.search(text):
        return "provider-payment-required"
    if 429 in stops and _RATE.search(text):
        return "provider-rate-limited"
    return None


def _default_fetch(url: str, timeout: float) -> str:
    """GET a public page. https only, no credentials, bounded size."""
    if not url.startswith("https://"):
        raise ValueError("only https urls are fetched")
    req = urllib.request.Request(url, headers={"User-Agent": "provider-limits-verifier/1", "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(_MAX_PAGE_BYTES).decode("utf-8", errors="replace")


def _plain(markup: str) -> str:
    """Normalize fetched HTML into plain text for reference matching."""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("’", "'").replace("‘", "'").replace("`", "")
    return re.sub(r"\s+", " ", text)


def verify_live(
    policy: Mapping[str, Any], fetch: Callable[[str, float], str] | None = None, timeout: float = 20
) -> dict:
    """Fetch each official reference and check every fact. Never raises.

    Per fact: confirmed (the pattern is on the page), drift (the page loaded but no longer says it),
    unreachable (the fetch failed). ok only when every fact is confirmed.
    """
    get = fetch or _default_fetch
    results = []
    for ref in policy["official_references"]:
        try:
            page = _plain(get(ref["url"], timeout))
            error = None
        except Exception as exc:  # network, TLS, size, decode: all are "could not confirm"
            page, error = None, f"{type(exc).__name__}: {exc}"
        for fact in ref["facts"]:
            if page is None:
                status = "unreachable"
            else:
                status = "confirmed" if re.search(fact["expect"], page, re.I) else "drift"
            results.append({"reference": ref["id"], "fact": fact["id"], "status": status,
                            **({"error": error} if error else {})})
    counts = {s: sum(r["status"] == s for r in results) for s in ("confirmed", "drift", "unreachable")}
    return {"ok": counts["drift"] == 0 and counts["unreachable"] == 0, "provider": policy["provider"],
            "results": results, **counts}


class _QuietParser(argparse.ArgumentParser):
    """An argument parser that never echoes the arguments it rejected (one of them could be a secret)."""

    def error(self, message: str) -> None:  # type: ignore[override]
        """Exit on invalid arguments without echoing potentially secret input."""
        print("refused: invalid arguments", file=sys.stderr)
        raise SystemExit(2)


def _is_interactive() -> bool:
    """True only when both stdin and stdout are a terminal, i.e. a person is at the keyboard."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _attest(args: argparse.Namespace) -> int:
    """Require an interactive confirmation before writing an operator attestation."""
    policy = load_policy(args.provider)
    problems = []
    for flag in ("plan_free", "payg_inactive", "allowance_remaining"):
        if not getattr(args, flag):
            problems.append(f"--{flag.replace('_', '-')} is required")
    if not (args.by and args.by.strip()):
        problems.append("--by is required")
    if not _is_interactive():
        problems.append("attest needs an interactive terminal; it cannot be confirmed any other way")
    if problems:
        print("refused: " + "; ".join(problems), file=sys.stderr)
        return 2
    # The phrase is shown only here, on a terminal, to the person who must type it.
    typed = input(f'Type exactly "{ATTEST_PHRASE}" to attest: ')
    if typed != ATTEST_PHRASE:
        print("refused: the typed confirmation did not match", file=sys.stderr)
        return 2
    facts = {"plan_is_free": args.plan_free, "payg_inactive": args.payg_inactive,
             "allowance_remaining": args.allowance_remaining}
    path = write_attestation_record(policy["provider"], args.by, facts, datetime.now(timezone.utc),
                                   presence_proof=typed)
    print(f"attestation written: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch the provider policy status, verification, or attestation command."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "attest":
        ap = _QuietParser(prog="provider_limits attest", add_help=False)
        ap.add_argument("cmd")
        ap.add_argument("provider")
        ap.add_argument("--plan-free", action="store_true", dest="plan_free")
        ap.add_argument("--payg-inactive", action="store_true", dest="payg_inactive")
        ap.add_argument("--allowance-remaining", action="store_true", dest="allowance_remaining")
        ap.add_argument("--by", default="")
        try:
            return _attest(ap.parse_args(args))
        except SystemExit:
            return 2
    if len(args) != 2 or args[0] not in ("verify", "status"):
        print("usage: python3 -m orchestrator.provider_limits {verify|status} <provider>\n"
              "       python3 -m orchestrator.provider_limits attest <provider> --plan-free --payg-inactive "
              "--allowance-remaining --by <name>   (operator only, interactive terminal)", file=sys.stderr)
        return 2
    policy = load_policy(args[1])
    if args[0] == "verify":
        out = verify_live(policy)
        for r in out["results"]:
            print(f"{r['status']:12} {r['reference']}/{r['fact']}")
        print(f"confirmed {out['confirmed']}  drift {out['drift']}  unreachable {out['unreachable']}")
        return 0 if out["ok"] else 1
    print(json.dumps({k: policy[k] for k in ("provider", "policy_id", "budget", "stop_on_http")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
