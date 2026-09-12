# PR #389 ChatGPT Shared Report Source Pointer

## Source

- Shared report: https://chatgpt.com/s/t_6aa5877cacc081918a2f714c7af3a17c
- Requested import date: 2026-09-13
- Target: PR #389, `.agent` memory

## Retrieval status

The full report body has **not** been imported yet because the active ChatGPT Work runtime could not retrieve the shared page:

- web fetch returned a cache miss for the exact shared URL;
- the execution sandbox could not resolve `chatgpt.com` through DNS;
- prior conversation/file context did not contain the exact shared-report body.

This file is intentionally a source pointer and retrieval-status record only. It must not be treated as the report itself, a summary of the report, or evidence for claims allegedly contained in the report.

## Required completion rule

When the shared page becomes retrievable, preserve the report as source evidence before synthesizing it:

1. fetch the exact shared report;
2. save its full text under `.agent/memory/working/` with source provenance;
3. verify byte/character counts and source markers after the remote write;
4. then cross-link or synthesize it into semantic/domain memory without rewriting accepted historical records in place.

Until those steps complete, future agents must treat the report content as unavailable rather than reconstructing or guessing it from surrounding context.
