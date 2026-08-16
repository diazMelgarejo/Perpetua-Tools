/**
 * ESM entry point for @diazmelgarejo/alphaclaw-adapter.
 *
 * Thin wrapper only -- all real logic lives in index.js (CJS), the single
 * implementation. This re-exports it for `import` consumers so both CJS
 * `require()` and ESM `import` work against the exact same runtime module,
 * never two divergent copies.
 */
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const adapter = require("./index.js");

export const {
  configure,
  DEFAULT_PORT,
  DEFAULT_HOST,
  ALPHACLAW_ROOT,
  CANDIDATE_PORTS,
  login,
  logout,
  authStatus,
  health,
  onboardStatus,
  status,
  gatewayStatus,
  gatewayDashboard,
  restartGateway,
  restartStatus,
  dismissRestartStatus,
  version,
  getModels,
  getModelsConfig,
  putModelsConfig,
  getEnv,
  putEnv,
  watchdogStatus,
  watchdogEvents,
  watchdogLogs,
  watchdogLogTailBytes,
  watchdogRepair,
  tailLogs,
  discoverPort,
  startServer,
  stopServer,
  waitForReady,
  ensureRunning,
  defaultPidFile,
} = adapter;

export default adapter;
