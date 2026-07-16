/**
 * Tool-handler tests for the 8 tools added in the AlphaClaw MCP tool-parity
 * migration (see docs/plans/2026-05-22-alphaclaw-wiring-migration-v2-satellites.md
 * Goal 2 Phase A). These exercise the exported building blocks behind the
 * 4 file-based tools directly (readConfigFile/readLogTail/readEnvVars back
 * alphaclaw_read_config/alphaclaw_tail_logs/alphaclaw_check_env, and
 * alphaclaw_list_providers derives from readConfigFile's output). The 2
 * process-spawning tools (alphaclaw_build_ui, alphaclaw_run_tests) and the
 * 2 adapter-backed local_agent tools are integration-level (spawn npm/vitest,
 * or require a running gateway) and are intentionally out of scope for this
 * fast unit suite — covered by manual verification per Task 2A.1.
 *
 * Run: node --test packages/alphaclaw-mcp/tests/tool-handlers.test.mjs
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexPath = path.resolve(__dirname, "../build/index.js");

async function loadModule() {
  return import(pathToFileURL(indexPath).href);
}

function makeTmpRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "alphaclaw-mcp-test-"));
}

describe("readConfigFile (backs alphaclaw_read_config + alphaclaw_list_providers)", () => {
  it("reports not configured when the config file is absent", async () => {
    const { readConfigFile } = await loadModule();
    const root = makeTmpRoot();
    const result = readConfigFile(path.join(root, "openclaw.json"), [root]);
    assert.equal(result.configured, false);
    assert.match(result.message ?? "", /not found/i);
  });

  it("reads and returns providers from a valid config, redacting secrets", async () => {
    const { readConfigFile } = await loadModule();
    const root = makeTmpRoot();
    const configPath = path.join(root, "openclaw.json");
    fs.writeFileSync(
      configPath,
      JSON.stringify({
        gateway: {
          providers: {
            anthropic: { enabled: true, models: ["claude-sonnet-5"], apiKey: "sk-secret-value" },
          },
        },
      }),
    );
    const result = readConfigFile(configPath, [root]);
    assert.equal(result.configured, true);
    // Secret must be redacted, never returned verbatim.
    assert.doesNotMatch(JSON.stringify(result.config), /sk-secret-value/);
  });

  it("refuses to read outside the approved roots (path gate)", async () => {
    const { readConfigFile } = await loadModule();
    const root = makeTmpRoot();
    const outside = makeTmpRoot();
    const outsideConfig = path.join(outside, "openclaw.json");
    fs.writeFileSync(outsideConfig, JSON.stringify({ providers: {} }));
    const result = readConfigFile(outsideConfig, [root]);
    assert.equal(result.configured, false);
    assert.ok(result.error, "expected a path-gate error");
  });
});

describe("readLogTail (backs alphaclaw_tail_logs)", () => {
  it("reports not found when the log file is absent", async () => {
    const { readLogTail } = await loadModule();
    const root = makeTmpRoot();
    const result = readLogTail(path.join(root, "hourly-sync.log"), [root], 50);
    assert.equal(result.found, false);
  });

  it("returns the last N lines and redacts secrets", async () => {
    const { readLogTail } = await loadModule();
    const root = makeTmpRoot();
    const logPath = path.join(root, "hourly-sync.log");
    const lines = Array.from({ length: 10 }, (_, i) => `line ${i}`);
    lines[8] = "SETUP_PASSWORD=supersecret";
    fs.writeFileSync(logPath, lines.join("\n"));
    const result = readLogTail(logPath, [root], 3);
    assert.equal(result.found, true);
    assert.equal(result.lines, 3);
    assert.match(result.log ?? "", /line 9/);
    assert.doesNotMatch(result.log ?? "", /line 6/);
    assert.doesNotMatch(result.log ?? "", /supersecret/);
    assert.match(result.log ?? "", /\[REDACTED\]/);
  });

  it("clamps a negative/NaN/Infinity line count to the 50-line default", async () => {
    const { readLogTail } = await loadModule();
    const root = makeTmpRoot();
    const logPath = path.join(root, "hourly-sync.log");
    fs.writeFileSync(logPath, Array.from({ length: 60 }, (_, i) => `l${i}`).join("\n"));

    for (const invalidCount of [-5, NaN, Infinity]) {
      const result = readLogTail(logPath, [root], invalidCount);
      assert.equal(result.lines, 50, `Failed clamping for ${invalidCount}`);
    }
  });

  it("caps an oversized line count at 200", async () => {
    const { readLogTail } = await loadModule();
    const root = makeTmpRoot();
    const logPath = path.join(root, "hourly-sync.log");
    fs.writeFileSync(logPath, Array.from({ length: 300 }, (_, i) => `l${i}`).join("\n"));
    const result = readLogTail(logPath, [root], 999999);
    assert.equal(result.lines, 200);
  });
});

describe("readEnvVars (backs alphaclaw_check_env)", () => {
  it("reports missing when .env does not exist", async () => {
    const { readEnvVars } = await loadModule();
    const root = makeTmpRoot();
    const result = readEnvVars(path.join(root, ".env"), [root]);
    assert.equal(result.env_file, false);
    assert.equal(result.setup_password, false);
  });

  it("detects a present SETUP_PASSWORD without revealing its value", async () => {
    const { readEnvVars } = await loadModule();
    const root = makeTmpRoot();
    const envPath = path.join(root, ".env");
    fs.writeFileSync(envPath, "SETUP_PASSWORD=hunter2\nOTHER=1\n");
    const result = readEnvVars(envPath, [root]);
    assert.equal(result.env_file, true);
    assert.equal(result.setup_password, true);
    assert.doesNotMatch(JSON.stringify(result), /hunter2/);
  });

  it("reports missing SETUP_PASSWORD when .env exists without it", async () => {
    const { readEnvVars } = await loadModule();
    const root = makeTmpRoot();
    const envPath = path.join(root, ".env");
    fs.writeFileSync(envPath, "OTHER=1\n");
    const result = readEnvVars(envPath, [root]);
    assert.equal(result.env_file, true);
    assert.equal(result.setup_password, false);
  });
});
