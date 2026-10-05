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
  assert.deepEqual(ids, [...ids].sort().reverse());
  sqlite.close();
});

test('subsequent pages use an indexed ID range instead of a cursor OR scan', async () => {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  let plan = '';
  const db = { prepare(sql) { return { bind(...args) { return { async all() {
    plan = sqlite.prepare(`EXPLAIN QUERY PLAN ${sql}`).all(...args).map(row => row.detail).join('\n');
    return { results: sqlite.prepare(sql).all(...args) };
  } }; } }; } };
  await new api.PromptStore(db).list('alice', { before: 'cursor', limit: 2 });
  assert.match(plan, /id<\?/);
  sqlite.close();
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
