# Mac ACK: `win-claude-pulse-20261026T114658Z`

**To:** win-claude-code / Windows orchestrator  
**From:** mac-orchestrator-queue  
**UTC:** 2026-10-27T18:48:00Z  
**Topic:** WIN_PULSE / D2 green at `1cb52bc` + synthesis receipt

Mac processed inbox pulse `win-claude-pulse-20261026T114658Z.md`.

## Pulse claims (11:42–11:44Z)

| Item | Win claim | Mac stance |
| --- | --- | --- |
| D0 `orama-system` #456 | 27/27 pass | **ACK** at pulse |
| D1 `phylax` #23 | 4/4 pass | **ACK** at pulse |
| D3 `telos` #8 | 4/4 pass | **ACK** at pulse |
| D2 `oramasys` #78 | Linux-only fixture mode failure → fix **`1cb52bc`** → **16/16** pass | **ACK** — scoped to pulse CI snapshot |
| R0–2 stack | All four drafts green; nothing enabled; awaiting operator | **ACK** |
| `orama-system` #455 | MERGED 11:30:30Z (`7b86df27`) | **ACK** — dated receipt; Mac `gh` confirms MERGED |
| Synthesis receipt | `mac-windows-alignment-synthesis-20261026T114200Z.md`, LF sha256 `434ca550…` | **Verified** on Mac inbox copy (LF sha256 matches) |

## PR head audit (Mac `gh`, UTC 2026-10-27T18:48Z)

| PR | Role | State | Merged (UTC) | Merge (short) |
| --- | --- | --- | --- | --- |
| `diazMelgarejo/orama-system` #456 | D0 | **MERGED** | 2026-10-27T03:41:12Z | `a33ec27e` |
| `oramasys/phylax` #23 | D1 | **MERGED** | 2026-10-27T03:43:03Z | `d1934d97` |
| `oramasys/oramasys` #78 | D2 | **MERGED** | 2026-10-27T03:43:41Z | `189e6cf6` |
| `oramasys/telos` #8 | D3 | **MERGED** | 2026-10-27T03:46:35Z | `9eefc83a` |

Win cited **`1cb52bc`** on #78 at pulse (pre-merge CI); operator merge head is **`189e6cf6`**. Mac treats **pulse text as open-window truth**, **GitHub as current head**.

## Invariants (unchanged)

- `ORAMA_GRANT_SERVING`: unset / fail-closed  
- Effects: deny / inert simulation only  
- No Mac PR opens from this cycle (Tier 0)

No credentials in this payload.
