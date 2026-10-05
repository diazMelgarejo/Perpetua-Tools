import assert from 'node:assert/strict';
import test from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';

const api = await import('../src/index.mjs');

function database() {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  return {
    prepare(sql) {
      let args = [];
      return {
        bind(...values) { args = values; return this; },
        async run() { return sqlite.prepare(sql).run(...args); },
        async first() { return sqlite.prepare(sql).get(...args) ?? null; },
        async all() { return { results: sqlite.prepare(sql).all(...args) }; },
      };
    },
  };
}

test('compiler preserves original bytes and labels deterministic output', () => {
  assert.equal(typeof api.compilePrompt, 'function');
  const original = '  Explain \u03bb\r\n\n';
  const output = api.compilePrompt({ original, role: 'Teacher', goal: 'Explain', constraints: 'Cite evidence', output_format: 'Table' });
  assert.equal(output.original, original);
  assert.equal(output.mode, 'structured-contract');
  assert.match(output.improved, /ROLE\/CONTEXT\nTeacher/);
  assert.match(output.improved, /OUTPUT FORMAT\nTable/);
});

test('invalid input fails before persistence', () => {
  assert.equal(typeof api.compilePrompt, 'function');
  for (const original of ['', '   ', 'x'.repeat(32769)]) {
    assert.throws(() => api.compilePrompt({ original }), /original/);
  }
  assert.throws(() => api.compilePrompt({ original: 'task', owner: 'spoof' }), /Unknown/);
});

test('records isolate owners and retry without duplication or overwriting', async () => {
  assert.equal(typeof api.PromptStore, 'function');
  const store = new api.PromptStore(database());
  const record = api.compilePrompt({ original: 'Original', goal: 'Answer' });
  const first = await store.save('alice', 'retry-key', record);
  assert.deepEqual(await store.save('alice', 'retry-key', record), first);
  await assert.rejects(store.save('alice', 'retry-key', { ...record, original: 'Changed' }), /conflict/);
  assert.equal(await store.get('bob', first.id), null);
  assert.equal((await store.list('alice')).items.length, 1);
  assert.equal((await store.list('bob')).items.length, 0);
  await store.archive('bob', first.id);
  assert.equal((await store.get('alice', first.id)).archived, 0);
  await store.archive('alice', first.id);
  assert.equal((await store.list('alice')).items.length, 0);
  assert.equal((await store.get('alice', first.id)).original, 'Original');
});

test('owner and pagination are server validated', async () => {
  assert.equal(typeof api.PromptStore, 'function');
  const store = new api.PromptStore(database());
  await assert.rejects(store.list(''), /authenticated/);
  await assert.rejects(store.list('alice', { limit: 10000 }), /limit/);
});

test('schema reapplication retains records and pagination traverses every unchanged record', async () => {
  const sqlite = new DatabaseSync(':memory:');
  const schema = readFileSync(new URL('../schema.sql', import.meta.url), 'utf8');
  sqlite.exec(schema);
  const db = { prepare(sql) { let args = []; return {
    bind(...values) { args = values; return this; },
    async run() { return sqlite.prepare(sql).run(...args); },
    async first() { return sqlite.prepare(sql).get(...args) ?? null; },
    async all() { return { results: sqlite.prepare(sql).all(...args) }; },
  }; } };
  const store = new api.PromptStore(db);
  for (let i = 0; i < 7; i++) await store.save('alice', `key-${i}`, api.compilePrompt({ original: `source-${i}` }));
  sqlite.exec(schema);
  const ids = []; let before = '';
  do { const page = await store.list('alice', { limit: 2, before }); ids.push(...page.items.map(r => r.id)); before = page.next_cursor; } while (before);
  assert.equal(ids.length, 7);
  assert.equal(new Set(ids).size, 7);
  sqlite.close();
});

test('subsequent pages use the (created_at, id) history index', async () => {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  let plan = '';
  const db = { prepare(sql) { return { bind(...args) { return { async all() {
    plan = sqlite.prepare(`EXPLAIN QUERY PLAN ${sql}`).all(...args).map(row => row.detail).join('\n');
    return { results: sqlite.prepare(sql).all(...args) };
  } }; } }; } };
  await new api.PromptStore(db).list('alice', { before: '2026-10-05T00:00:00.000Z|cursor', limit: 2 });
  assert.match(plan, /USING (COVERING )?INDEX prompt_records_owner_history/);
  assert.doesNotMatch(plan, /USE TEMP B-TREE/);
  sqlite.close();
});

test('history is newest-first by (created_at, id), independent of random UUID order', async () => {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  const db = { prepare(sql) { let args = []; return {
    bind(...values) { args = values; return this; },
    async all() { return { results: sqlite.prepare(sql).all(...args) }; },
  }; } };
  const insert = sqlite.prepare("INSERT INTO prompt_records (owner_id, id, request_key, original, improved, mode, version, created_at) VALUES ('alice', ?, ?, 'o', 'i', 'structured-contract', '1.0.0', ?)");
  // zzz is the lexically largest id but the oldest record; aaa/bbb share a millisecond.
  insert.run('zzz', 'k1', '2026-10-05T10:00:00.000Z');
  insert.run('aaa', 'k2', '2026-10-05T11:00:00.000Z');
  insert.run('bbb', 'k3', '2026-10-05T11:00:00.000Z');
  insert.run('ccc', 'k4', '2026-10-05T12:00:00.000Z');
  const store = new api.PromptStore(db);
  const ids = []; let before = '';
  do { const page = await store.list('alice', { limit: 1, before }); ids.push(...page.items.map(r => r.id)); before = page.next_cursor; } while (before);
  assert.deepEqual(ids, ['ccc', 'bbb', 'aaa', 'zzz']);
  await assert.rejects(store.list('alice', { before: 'zzz' }), /cursor/);
  sqlite.close();
});

test('save enforces UTF-8 byte bounds on stored records', async () => {
  const store = new api.PromptStore(database());
  const ok = api.compilePrompt({ original: 'ok' });
  const wide = '\u03bb'.repeat(16385); // 32770 bytes, only 16385 characters
  await assert.rejects(store.save('alice', 'wide', { ...ok, original: wide }), /UTF-8 bytes/);
  await assert.rejects(store.save('alice', 'blank', { ...ok, original: '   ' }), /original/);
  await assert.rejects(store.save('alice', 'huge', { ...ok, improved: 'x'.repeat(200000) }), /improved/);
  await assert.rejects(store.save('alice', 'nil', null), /Invalid prompt record/);
  assert.equal((await store.list('alice')).items.length, 0);
  await store.save('alice', 'edge', api.compilePrompt({ original: '\u03bb'.repeat(16384) }));
});

test('history pages return short previews without embedding full contracts', async () => {
  const store = new api.PromptStore(database());
  const original = 'λ'.repeat(10000);
  const saved = await store.save('alice', 'large', api.compilePrompt({ original }));
  const item = (await store.list('alice')).items[0];
  assert.equal(item.original_preview, 'λ'.repeat(240));
  assert.equal(Object.hasOwn(item, 'improved'), false);
  assert.equal(Object.hasOwn(item, 'original'), false);
  assert.equal((await store.get('alice', saved.id)).original, original);
});
