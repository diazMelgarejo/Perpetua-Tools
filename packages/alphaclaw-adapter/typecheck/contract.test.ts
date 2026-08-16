/**
 * Type-contract fixture for @diazmelgarejo/alphaclaw-adapter.
 *
 * Not a runtime test -- compiled with `tsc --noEmit` only, to prove the
 * package's published types are both present (valid calls resolve, no
 * @ts-ignore needed) and enforced (invalid calls are rejected, not
 * silently typed as `any`). Mirrors the exact import style
 * packages/alphaclaw-mcp/src/index.ts needs to use without @ts-ignore.
 */
import adapter from "@diazmelgarejo/alphaclaw-adapter";

// ── Valid calls: must type-check clean ──────────────────────────────────
async function validCalls(): Promise<void> {
  const h = await adapter.health();
  if (h.ok) {
    console.log(h.status);
  }

  const login = await adapter.login("some-password");
  console.log(login.authenticated);

  adapter.configure({ host: "127.0.0.1", port: 3000 });

  const discovered = await adapter.discoverPort("127.0.0.1", [3000, 3001], 2000);
  if (discovered.found) {
    console.log(discovered.port);
  }

  const started = await adapter.startServer({ port: 3000, alphaclawRoot: "/tmp" });
  console.log(started.ok);

  const ready = await adapter.ensureRunning({ port: 3000 });
  console.log(ready.commandeered);

  await adapter.stopServer({ signal: "SIGTERM", graceMs: 5000 });
}

// ── Invalid calls: MUST be rejected by tsc, proving types are enforced ──
// @ts-expect-error - login requires a string password, not a number
adapter.login(12345);
// @ts-expect-error - configure's port must be a number, not a string
adapter.configure({ port: "not-a-number" });
// @ts-expect-error - unknown top-level export must not silently exist
adapter.thisFunctionDoesNotExist();

void validCalls;
