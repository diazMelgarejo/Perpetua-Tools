# Stray Folder Remediation

Date: 2026-07-09

## Endpoint policy contract

The endpoint transport policy contract is required at `.agent/endpoint-policy-contract.yml` for CI. The copy under `.agent/protocols/endpoint-policy-contract.yml` was a relocation mistake and has been removed.

The reusable endpoint policy primitive lives as a subpackage under `packages/endpoint-policy/`. That subpackage carries its own Apache-2.0 license metadata, `LICENSE`, and `NOTICE`, so downstream consumers can adopt the contract without inheriting the host repository license.

## `--help/` memory folder

The root `--help/` directory was a stray memory-render output location. Its files contained only the default `LESSONS.md` render stub and an empty `lessons.jsonl`; there was no unique semantic content to merge into `.agent/memory/semantic/`.

Probable root cause: a rogue agent invoked a memory-render or learning command with a malformed argument list, causing `--help` to be interpreted as a path rather than a flag. Future agents must pass `--` before user-supplied strings that may start with `-`, and must verify output paths before writing generated memory files.

Canonical semantic memory remains under `.agent/memory/semantic/`.
