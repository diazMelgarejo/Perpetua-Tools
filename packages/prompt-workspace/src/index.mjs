/** Portable prompt contracts and D1 persistence. No inference or local-machine access. */
export const VERSION = '1.0.0';
const encoder = new TextEncoder();
const fields = ['original', 'role', 'goal', 'constraints', 'output_format'];

/** @param {unknown} input @returns {{original:string, improved:string, mode:string, version:string}} */
export function compilePrompt(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Input must be an object');
  for (const key of Object.keys(input)) if (!fields.includes(key)) throw new Error(`Unknown field: ${key}`);
  for (const key of fields) {
    const value = input[key];
    if (value !== undefined && (typeof value !== 'string' || encoder.encode(value).length > 32768)) {
      throw new Error(`${key} must be a string of at most 32768 UTF-8 bytes`);
    }
  }
  if (typeof input.original !== 'string' || !input.original.trim()) throw new Error('original is required');
  const sections = [
    ['ROLE/CONTEXT', input.role || 'State the expertise needed for the task.'],
    ['GOAL/TASK', input.goal || input.original],
    ['CONSTRAINTS', input.constraints || 'Preserve the request. Label assumptions and uncertainty. Do not invent facts.'],
    ['OUTPUT FORMAT', input.output_format || 'Give the result, supporting evidence, limitations, and concrete next actions.'],
    ['ORIGINAL INPUT (preserve as source)', input.original],
  ];
  return { original: input.original, improved: sections.map(([label, text]) => `${label}\n${text}`).join('\n\n'), mode: 'structured-contract', version: VERSION };
}

/** @param {string} owner @returns {void} */
function requireOwner(owner) {
  if (typeof owner !== 'string' || !owner || owner.length > 512) throw new Error('authenticated owner required');
}

/** @param {string} value @returns {void} */
function requireId(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(value)) throw new Error('Invalid record ID or request key');
}

export class PromptStore {
  /** @param {object} db D1-compatible prepared-statement binding. */
  constructor(db) { if (!db?.prepare) throw new Error('Prompt storage unavailable'); this.db = db; }

  /** @param {string} owner @param {string} requestKey @param {object} record @returns {Promise<object>} */
  async save(owner, requestKey, record) {
    requireOwner(owner); requireId(requestKey);
    if (record.mode !== 'structured-contract' || record.version !== VERSION || typeof record.original !== 'string' || typeof record.improved !== 'string') throw new Error('Invalid prompt record');
    const id = crypto.randomUUID();
    await this.db.prepare('INSERT INTO prompt_records (owner_id, id, request_key, original, improved, mode, version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(owner_id, request_key) DO NOTHING')
      .bind(owner, id, requestKey, record.original, record.improved, record.mode, record.version, new Date().toISOString()).run();
    const saved = await this.db.prepare('SELECT id, original, improved, mode, version, created_at, archived FROM prompt_records WHERE owner_id = ? AND request_key = ?').bind(owner, requestKey).first();
    if (!saved || saved.original !== record.original || saved.improved !== record.improved || saved.mode !== record.mode || saved.version !== record.version) throw new Error('Idempotency conflict: use a new request key for changed input');
    return saved;
  }

  /** @param {string} owner @param {string} id @returns {Promise<object|null>} */
  async get(owner, id) {
    requireOwner(owner); requireId(id);
    return this.db.prepare('SELECT id, original, improved, mode, version, created_at, archived FROM prompt_records WHERE owner_id = ? AND id = ?').bind(owner, id).first();
  }

  /** @param {string} owner @param {{limit?:number,before?:string}} options @returns {Promise<object>} */
  async list(owner, { limit = 20, before = '' } = {}) {
    requireOwner(owner);
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) throw new Error('limit must be 1..50');
    if (typeof before !== 'string' || before.length > 128) throw new Error('Invalid cursor');
    // UUID cursor, ordered lexically, is deterministic even for same-millisecond creates.
    const query = 'SELECT id, substr(original, 1, 240) AS original_preview, mode, version, created_at, archived FROM prompt_records WHERE owner_id = ? AND archived = 0';
    const statement = this.db.prepare(query + (before ? ' AND id < ?' : '') + ' ORDER BY id DESC LIMIT ?');
    const { results } = await statement.bind(...(before ? [owner, before, limit + 1] : [owner, limit + 1])).all();
    const items = results.slice(0, limit);
    return { items, next_cursor: results.length > limit ? items.at(-1).id : null };
  }

  /** @param {string} owner @param {string} id @returns {Promise<object|null>} */
  async archive(owner, id) {
    requireOwner(owner); requireId(id);
    await this.db.prepare('UPDATE prompt_records SET archived = 1 WHERE owner_id = ? AND id = ?').bind(owner, id).run();
    return this.get(owner, id);
  }
}
