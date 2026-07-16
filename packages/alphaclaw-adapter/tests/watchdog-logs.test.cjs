/**
 * watchdogLogs query mapping — gateway expects ?tail=<bytes>, not ?lines=.
 * Run: node --test packages/alphaclaw-adapter/tests/watchdog-logs.test.cjs
 */

"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { watchdogLogTailBytes } = require("../src/index.js");

describe("watchdogLogTailBytes", () => {
  it("defaults invalid input to 50 lines (~25 KiB)", () => {
    assert.equal(watchdogLogTailBytes(-1), 50 * 512);
    assert.equal(watchdogLogTailBytes(NaN), 50 * 512);
    assert.equal(watchdogLogTailBytes(Infinity), 50 * 512);
  });

  it("caps at 200 lines and 65536 bytes", () => {
    assert.equal(watchdogLogTailBytes(999), 65536);
    assert.equal(watchdogLogTailBytes(200), 65536);
    assert.equal(watchdogLogTailBytes(100), 100 * 512);
  });

  it("enforces a 1024-byte minimum tail window", () => {
    assert.equal(watchdogLogTailBytes(1), 1024);
  });

  it("scales line count to bytes", () => {
    assert.equal(watchdogLogTailBytes(10), 10 * 512);
  });
});
