/**
 * Type declarations for @diazmelgarejo/alphaclaw-adapter.
 *
 * Hand-written to match src/index.js's real module.exports surface exactly
 * (function-by-function, not inferred) -- verified against
 * typecheck/contract.test.ts via `tsc --noEmit`, not assumed correct.
 */

export interface ConfigureOpts {
  host?: string;
  port?: number;
}

export interface HealthResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
}

export interface AuthStatusResult {
  ok: boolean;
  authenticated?: boolean;
  [key: string]: unknown;
}

export interface LoginResult {
  ok: boolean;
  authenticated: boolean;
  status?: number;
  body?: unknown;
  error?: string;
}

export interface LogoutResult {
  ok: boolean;
}

export interface OnboardStatusResult {
  ok: boolean;
  onboarded?: boolean;
  [key: string]: unknown;
}

export interface StatusResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
}

export interface GatewayStatusResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
}

export interface GatewayDashboardResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
}

export interface GenericApiResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
  [key: string]: unknown;
}

export interface DiscoverPortResult {
  found: boolean;
  port?: number;
  host?: string;
}

export interface StartServerOpts {
  port?: number;
  alphaclawRoot?: string;
  logFile?: string;
  pidFile?: string;
}

export interface StartServerResult {
  ok: boolean;
  already?: boolean;
  pid?: number;
  port: number;
  pidFile?: string;
  error?: string;
}

export interface StopServerOpts {
  alphaclawRoot?: string;
  pidFile?: string;
  signal?: string;
  graceMs?: number;
}

export interface StopServerResult {
  ok: boolean;
  already?: boolean;
  stopped?: boolean;
  forced?: boolean;
  port?: number;
  pid?: number;
  error?: string;
}

export interface WaitForReadyOpts {
  timeoutMs?: number;
  intervalMs?: number;
}

export interface WaitForReadyResult {
  ready: boolean;
  elapsed: number;
  error?: string;
}

export interface EnsureRunningResult {
  ok: boolean;
  commandeered?: boolean;
  started?: boolean;
  port: number;
  pid?: number;
  elapsed?: number;
  error?: string;
}

export const DEFAULT_PORT: number;
export const DEFAULT_HOST: string;
export const ALPHACLAW_ROOT: string;
export const CANDIDATE_PORTS: number[];

export function configure(opts?: ConfigureOpts): void;

export function login(password: string): Promise<LoginResult>;
export function logout(): Promise<LogoutResult>;
export function authStatus(): Promise<AuthStatusResult>;

export function health(): Promise<HealthResult>;
export function onboardStatus(): Promise<OnboardStatusResult>;

export function status(): Promise<StatusResult>;
export function gatewayStatus(): Promise<GatewayStatusResult>;
export function gatewayDashboard(): Promise<GatewayDashboardResult>;
export function restartGateway(): Promise<GenericApiResult>;
export function restartStatus(): Promise<GenericApiResult>;
export function dismissRestartStatus(): Promise<GenericApiResult>;
export function version(): Promise<GenericApiResult>;

export function getModels(): Promise<GenericApiResult>;
export function getModelsConfig(): Promise<GenericApiResult>;
export function putModelsConfig(body: unknown): Promise<GenericApiResult>;
export function getEnv(): Promise<GenericApiResult>;
export function putEnv(body: unknown): Promise<GenericApiResult>;

export function watchdogStatus(): Promise<GenericApiResult>;
export function watchdogEvents(): Promise<GenericApiResult>;
export function watchdogLogs(lines?: number): Promise<GenericApiResult>;
export function watchdogLogTailBytes(bytes?: number): Promise<GenericApiResult>;
export function watchdogRepair(): Promise<GenericApiResult>;
export function tailLogs(lines?: number): Promise<GenericApiResult>;

export function discoverPort(
  host?: string,
  ports?: number[],
  timeoutMs?: number
): Promise<DiscoverPortResult>;
export function startServer(opts?: StartServerOpts): Promise<StartServerResult>;
export function stopServer(opts?: StopServerOpts): Promise<StopServerResult>;
export function waitForReady(opts?: WaitForReadyOpts): Promise<WaitForReadyResult>;
export function ensureRunning(opts?: StartServerOpts): Promise<EnsureRunningResult>;
export function defaultPidFile(alphaclawRoot?: string): string;

declare const _default: {
  configure: typeof configure;
  DEFAULT_PORT: typeof DEFAULT_PORT;
  DEFAULT_HOST: typeof DEFAULT_HOST;
  ALPHACLAW_ROOT: typeof ALPHACLAW_ROOT;
  CANDIDATE_PORTS: typeof CANDIDATE_PORTS;
  login: typeof login;
  logout: typeof logout;
  authStatus: typeof authStatus;
  health: typeof health;
  onboardStatus: typeof onboardStatus;
  status: typeof status;
  gatewayStatus: typeof gatewayStatus;
  gatewayDashboard: typeof gatewayDashboard;
  restartGateway: typeof restartGateway;
  restartStatus: typeof restartStatus;
  dismissRestartStatus: typeof dismissRestartStatus;
  version: typeof version;
  getModels: typeof getModels;
  getModelsConfig: typeof getModelsConfig;
  putModelsConfig: typeof putModelsConfig;
  getEnv: typeof getEnv;
  putEnv: typeof putEnv;
  watchdogStatus: typeof watchdogStatus;
  watchdogEvents: typeof watchdogEvents;
  watchdogLogs: typeof watchdogLogs;
  watchdogLogTailBytes: typeof watchdogLogTailBytes;
  watchdogRepair: typeof watchdogRepair;
  tailLogs: typeof tailLogs;
  discoverPort: typeof discoverPort;
  startServer: typeof startServer;
  stopServer: typeof stopServer;
  waitForReady: typeof waitForReady;
  ensureRunning: typeof ensureRunning;
  defaultPidFile: typeof defaultPidFile;
};

export default _default;
